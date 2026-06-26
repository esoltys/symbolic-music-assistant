Feature: Voice-Leading Validation
  As a harmony instructor
  I want to check a score for voice-leading violations
  So that parallel fifths and octaves are flagged

  Scenario: Detect parallel fifths between Soprano and Bass
    Given a soprano part with notes "C5" then "D5"
    And a bass part with notes "F3" then "G3"
    When the user requests to check the score for voice-leading errors
    Then the voice leading validator tool should be called
    And the response should report the parallel fifths violation
