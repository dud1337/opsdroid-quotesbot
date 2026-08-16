# Quotes Opsdroid

A simple bot to store quotes in the chat.

Requires mongodb due to custom collection commands

## More of a PoC - Be careful

## Example configuration:
```
 quotes_opdroid:
    path: /home/opsdroid/skills/quotes_opsdroid
    quotes_collection: "your_quotes"
    quotes_room: "!blah_blah:matrix.blah.blah"
    quotes_cron_interval: "6 0 1/3 * *"
```
