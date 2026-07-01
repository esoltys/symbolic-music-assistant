@in_order
Feature: Score Editing Operations
  As a music student
  I want to edit an existing score by removing/modifying notes and measures
  So that I can correct errors and refine my compositions

  Scenario: Delete a note and replace with a rest
    Given a clean score state
    When the user requests to initialize a blank score with time signature "4/4"
    Then the score should contain a blank note stream with signature "4/4"
    When the user requests to add note "C4" with duration "quarter"
    Then the score state file should contain a note token with pitch "C4" and duration "quarter"
    When the user requests to delete the note at measure 1 index 0
    Then the event at measure 1 index 0 should be a rest of duration "quarter"

  Scenario: Edit a note pitch and duration
    Given a clean score state
    When the user requests to initialize a blank score with time signature "4/4"
    Then the score should contain a blank note stream with signature "4/4"
    When the user requests to add note "C4" with duration "quarter"
    Then the score state file should contain a note token with pitch "C4" and duration "quarter"
    When the user requests to edit the note at measure 1 index 0 to pitch "E4" and duration "half"
    Then the event at measure 1 index 0 should be pitch "E4" and duration "half"

  Scenario: Insert and delete a measure
    Given a clean score state
    When the user requests to initialize a blank score with time signature "4/4"
    Then the score should contain a blank note stream with signature "4/4"
    When the user requests to add note "C4" with duration "quarter"
    And the user requests to add note "D4" with duration "half"
    When the user requests to insert a measure at measure index 1
    Then measure 1 should be empty
    And measure 2 should contain note "C4"
    When the user requests to delete measure 1
    Then measure 1 should contain note "C4"

  Scenario: Transpose a single part
    Given a clean score state
    When the user requests to initialize a blank score with time signature "4/4"
    And the user requests to add note "C4" with duration "quarter" to part "melody"
    And the user requests to add note "C3" with duration "quarter" to part "bassline"
    When the user requests to transpose part "bassline" by 2 semitones
    Then the part "melody" note at measure 1 index 0 should be pitch "C4"
    And the part "bassline" note at measure 1 index 0 should be pitch "D3"
