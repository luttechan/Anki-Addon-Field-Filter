# Field Filter for Anki Desktop

Adds a **Field Filter** checkbox next to the Anki Browser search box.

## Usage

1. Open **Browse** in Anki and enable **Field Filter**.
2. Choose a deck, then choose one of its fields.
3. Enter a search term and run the search.

The field list contains only fields used by notes with cards in the selected
deck or its subdecks. It also includes cards temporarily moved to a filtered
deck from that deck. Unused note types are excluded; empty decks have no fields.
The initial selection is Anki's current deck. Toggle Field Filter off and on
to refresh the deck list after changing your collection.

Searches are restricted to the selected deck (including subdecks) and field.
For example, deck `English`, field `Word`, and term `allocate` produce
`"deck:English" "Word:allocate"`.

When disabled, Anki search works normally.

## Install

Use **Tools → Add-ons → Install from file...** and select the `.ankiaddon` package.
Restart Anki after installing or updating the add-on.
