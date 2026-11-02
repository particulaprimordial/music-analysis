-- Particula Primordial: export selected REAPER MIDI take notes to CSV.
-- Select one or more MIDI media items, then run this ReaScript in REAPER.
-- Output is written to REAPER's resource directory so it can be found reliably.

local output_path = reaper.GetResourcePath() .. "/particula_primordial_midi_notes.csv"
local file, err = io.open(output_path, "w")
if not file then
  reaper.ShowMessageBox("Could not write CSV: " .. tostring(err), "Particula Primordial", 0)
  return
end

file:write("item_index,track_name,take_name,note_index,start_ppq,end_ppq,start_qn,end_qn,channel,pitch,velocity,muted\n")
local item_count = reaper.CountSelectedMediaItems(0)
local written = 0

local function csv_escape(value)
  local s = tostring(value or "")
  s = s:gsub('"', '""')
  return '"' .. s .. '"'
end

for item_index = 0, item_count - 1 do
  local item = reaper.GetSelectedMediaItem(0, item_index)
  local take = item and reaper.GetActiveTake(item)
  if take and reaper.TakeIsMIDI(take) then
    local track = reaper.GetMediaItem_Track(item)
    local _, track_name = reaper.GetTrackName(track, "")
    local take_name = reaper.GetTakeName(take) or "MIDI take"
    local _, note_count = reaper.MIDI_CountEvts(take)
    for note_index = 0, note_count - 1 do
      local ok, selected, muted, start_ppq, end_ppq, channel, pitch, velocity =
        reaper.MIDI_GetNote(take, note_index)
      if ok then
        local start_qn = reaper.MIDI_GetProjQNFromPPQPos(take, start_ppq)
        local end_qn = reaper.MIDI_GetProjQNFromPPQPos(take, end_ppq)
        file:write(table.concat({
          item_index,
          csv_escape(track_name),
          csv_escape(take_name),
          note_index,
          string.format("%.6f", start_ppq),
          string.format("%.6f", end_ppq),
          string.format("%.6f", start_qn),
          string.format("%.6f", end_qn),
          channel,
          pitch,
          velocity,
          muted and 1 or 0
        }, ",") .. "\n")
        written = written + 1
      end
    end
  end
end

file:close()
reaper.ShowMessageBox(
  "Exported " .. written .. " MIDI notes.\n\nCSV: " .. output_path,
  "Particula Primordial", 0
)
