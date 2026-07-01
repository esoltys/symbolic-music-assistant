@in_order
Feature: Chord Diagram Visualization
  As a music student
  I want to see beautiful visual aids (piano and guitar tabs) when asking about chords
  So that I can visualize fingering patterns and learn jazz harmony

  Scenario: Render piano keyboard chord diagram
    When the user asks to visualize chord "C,E,G" on piano
    Then the agent should call the render_chord_diagram tool for piano
    And the response should embed the generated piano chord image

  Scenario: Render guitar fretboard chord diagram
    When the user asks to visualize chord "C Major" on guitar
    Then the agent should call the render_chord_diagram tool for guitar
    And the response should embed the generated guitar chord image
