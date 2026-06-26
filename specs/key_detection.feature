Feature: Key Signature Detection
  As a music composition assistant
  I want to detect the key signature of a score or MIDI file
  So that I can analyze its musical key

  Scenario: Detect key of a G major score canvas
    Given a score initialized in "C Major"
    And notes "G4", "B4", "D5", "F#5" added to the melody
    When the user requests to detect the key of the score
    Then the key signature detection tool should be called
    And the response should contain the detected key "G Major"
