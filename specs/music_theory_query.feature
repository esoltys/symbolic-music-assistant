Feature: Music Theory Query Interval Calculations
  As a music theory assistant
  I want to calculate the interval between two note pitches in semitones
  So that users can verify musical intervals and scale relations

  Scenario: Calculate semitones between C4 and G4 (Perfect 5th)
    Given the start note is "C4"
    And the end note is "G4"
    When the user requests the semitone distance
    Then the calculation should succeed
    And the result should be 7 semitones
    And the interval name should be "Perfect 5th"

  Scenario: Handle an out-of-bounds notation entry gracefully
    Given the start note is "C9"
    And the end note is "G4"
    When the user requests the semitone distance
    Then the calculation should fail
    And the error response should mention "Note out of valid MIDI/pitch range"
