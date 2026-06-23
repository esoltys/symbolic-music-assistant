Feature: MIDI Analytics Metrics Extraction
  As a music composition assistant
  I want to analyze a local MIDI file
  So that I can extract tracks, tempo, and note counts

  @any_order
  Scenario: Process a valid local MIDI file and return metrics
    Given a valid MIDI file path "skills/midi_analytics/assets/sample.mid"
    When the user requests the MIDI metrics summary
    Then the agent should call the midi parser tool
    And the response should contain the note count 256
    And the response should contain the tempo 120
