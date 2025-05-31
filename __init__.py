######################################################################
#   
#   quotes bot
#       State quotes from matrix
#   
#   1. Save a quote
#   2. Edit a quote
#   3. Delete a quote 📝
#   4. React to a post to save a quote?
#
######################################################################
from aiohttp.web import Request
from opsdroid.skill import Skill
from opsdroid.matchers import match_regex, match_crontab, match_event, match_webhook, match_always
from opsdroid.events import Message, Reaction, Image, Video, RoomDescription

from asyncio import sleep
from motor.motor_asyncio import AsyncIOMotorClient

import re
from random import choice, choices, normalvariate

class Quotes(Skill):
    def __init__(self, *args, **kwargs):
        super(Quotes, self).__init__(*args, **kwargs)
        self.bot_was_last_message = False
        self.collection_name = self.config.get('quotes_collection')
        self.quotes_room = self.config.get('quotes_room')

        self.client = None
        self.db = None
        self.collection = None

    async def connect_to_mongodb(self):
        if not self.client:
            connect_string = 'mongodb://'
            connect_string += f'{self.opsdroid.config["databases"]["mongo"]["user"]}:{self.opsdroid.config["databases"]["mongo"]["password"]}'
            connect_string += f'@{self.opsdroid.config["databases"]["mongo"]["host"]}:{self.opsdroid.config["databases"]["mongo"]["port"]}'
            self.client = AsyncIOMotorClient(connect_string)
            self.db = self.client[self.opsdroid.config["databases"]["mongo"]["database"]]
            self.collection = self.db.get_collection(self.collection_name)

    ##################################################################
    #
    #   1. Avoid spamming
    #       The bot notifies if a stream is ongoing every hour
    #       if no one posts within that hour, it is superfluous;
    #       this functionality prevents that.
    #
    ##################################################################
    async def avoid_spam_send(self, msg):
        if not self.bot_was_last_message:
            await self.opsdroid.send(
                Message(
                    text=msg,
                    target=self.config.get('quotes_room')
                )
            )
            self.bot_was_last_message = True
        else:
            pass

    @match_always
    async def who_last_said(self, event):
        if hasattr(event, 'target') and event.target == self.config.get('quotes_room'):
            self.bot_was_last_message = False


     ##################################################################
    #
    #   2. Core functionality
    #       Connect to database
    #       Add quotes to database
    #       Remove quotes from database
    #       Delete quotes from database
    #
    ##################################################################
    async def add_quote(self, quote):
        orig_quote_id_confirmed = False
        while not orig_quote_id_confirmed:
            quote_id = 'Q' + str(''.join(choices('0123456789', k=3)))
            if await self.get_quote(quote_id) == "Quote ID not found":
                orig_quote_id_confirmed = True
    
        async with self.opsdroid.get_database("mongo").memory_in_collection(self.collection_name) as db:
            data = await db.put(quote_id, quote)
        return quote_id

    async def delete_quote(self, quote_id):
        async with self.opsdroid.get_database("mongo").memory_in_collection(self.collection_name) as db:
            result = await db.delete(quote_id)

    async def modify_quote(self, quote_id, quote):
        if self.get_quote(quote_id) == "Quote ID not found":
            return f'Quote {quote_id} not found'

        async with self.opsdroid.get_database("mongo").memory_in_collection(self.collection_name) as db:
             await db.put(quote_id, quote)
             return f'Quote {quote_id} edited'

    async def get_quote(self, quote_id):
        async with self.opsdroid.get_database("mongo").memory_in_collection(self.collection_name) as db:
            data = await db.get(quote_id)
            return data or "Quote ID not found"

    async def get_quote_list(self, search_string=None):
        '''get all quotes as a dict'''
        output = dict()
        cursor = self.collection.find({})
        entries = await cursor.to_list(length=None)

        for entry in entries:
            if not search_string:
                output[entry['key']] = entry['value']
            elif re.search(str(search_string), entry['value'], re.IGNORECASE):
                output[entry['key']] = entry['value']
        return output    

    async def get_rand_quote(self):
        quote_dict = await self.get_quote_list()
        try:
            rand_key = choice(list(quote_dict.keys()))
            return f'{rand_key}: {quote_dict[rand_key]}'
        except:
            return "No quotes"

    async def get_quote_count(self):
        '''get the count of all quotes'''
        count = await self.collection.count_documents({})
        return count


    ##################################################################
    #
    #   3. Automatic Functionality
    #       Spamming quotes every now and then
    #       and on request
    #       
    #
    ##################################################################
    @match_crontab('0 0 1/7 * *', timezone="Europe/Zurich")
    async def rand_quote_to_a_room(self):
        await self.connect_to_mongodb()
        rand_quote = await self.get_rand_quote()

        wait = -1
        while wait < 0:
            wait = int(normalvariate(12 * 60, 6 * 60))
        await sleep(wait * 60)

        await self.opsdroid.send(
            Message(
                text=f'🗣️{rand_quote}',
                target=self.quotes_room
            )
        )


    ##################################################################
    #
    #   2. Called
    #       Quote modification
    #       'memo' functionality
    #
    ##################################################################
    @match_regex('^!q$')
    async def quote_random(self, message):
        '''!q - Get a random quote'''
        await self.connect_to_mongodb()

        rand_quote = await self.get_rand_quote()
        await self.opsdroid.send(
            Message(
                text=f'🗣️{rand_quote}',
                target=message.target
            )
        )

    @match_regex('^!q (?P<quoteid>Q.{3})$$')
    async def quote_get_by_id(self, message):
        '''!q Q123 - show the quote with ID Q123'''
        await self.connect_to_mongodb()

        quote = await self.get_quote(message.entities['quoteid']['value'])
        await self.opsdroid.send(
            Message(
                text=f'🗣️{quote}',
                target=message.target
            )
        )
   
    @match_regex('^!q add (?P<quote>.+)$')
    async def quote_add(self, message):
        '''!q add This is a new quote - Add a new quote'''
        await self.connect_to_mongodb()

        quote_id = await self.add_quote(message.entities['quote']['value'])
        await self.opsdroid.send(
            Message(
                text=f"quote added with id: {quote_id}",
                target=message.target
            )
        )

    @match_regex('^!q delete (?P<quoteid>Q.{3})$')
    async def quote_delete(self, message):
        '''!q delete Q123 - Delete the quote with ID Q123'''
        await self.connect_to_mongodb()

        result = await self.delete_quote(message.entities['quoteid']['value'])
        await self.opsdroid.send(
            Message(
                text="OK",
                target=message.target
            )
        )

    @match_regex('^!q modify (?P<quoteid>Q.{3}) (?P<quote>.+)$')
    async def quote_modify(self, message):
        '''!q modify Q123 The new version of the quote'''
        await self.connect_to_mongodb()

        result = await self.modify_quote(
            message.entities['quoteid']['value'],
            message.entities['quote']['value']
        )
        await self.opsdroid.send(
            Message(
                text=result,
                target=message.target
            )
        )

    @match_regex('^!q count$')
    async def quote_count(self, message):
        '''!q count - Return total number of quotes'''
        await self.connect_to_mongodb()

        quote_count = await self.get_quote_count()
        await self.opsdroid.send(
            Message(
                text=f"{quote_count}",
                target=message.target
            )
        )

    @match_regex('^!q search (?P<search_string>.+)$')
    async def quote_search(self, message):
        '''!q search <search string> - Search the quotes'''
        await self.connect_to_mongodb()

        search_string = message.entities['search_string']['value']
        if len(search_string) < 3:
            output = 'Use at least 3 characters'
        else:
            quote_dict = await self.get_quote_list(search_string=search_string)
            output = ''
            for key, value in quote_dict.items():
                output += f'{key}: {value}\n'
            output.strip('\n')

            if output == '':
                output = "No results found"

        await self.opsdroid.send(
            Message(
                text=output,
                target=message.target
            )
        )

    @match_event(Reaction)
    async def reaction_expander(self, event):
        '''React to a message with 📝to save it as a quote'''
        await self.connect_to_mongodb()

        cond = event.emoji in ['📝', '🔖']
        cond &= isinstance(event.linked_event, Message)
        if cond and not re.search(str('Q.{3}'), str(event.linked_event.text)):
            await self.add_quote(event.linked_event.text)
            await event.respond(
                Reaction(
                    emoji='✅',
                    linked_event=event.linked_event
                )
            )

    @match_regex('^!help quotes')
    async def help_quotes(self, event):
        '''
        Return help string to user
        '''
        text = 'Usage:<br>'
        text += '<b>!q</b> | Show a random quote<br>'
        text += '<b>!q [quote id]</b> | Show a specific quote<br>'
        text += '<b>!q modify [quote id] [new quote text]</b> | Modify a quote<br>'
        text += '<b>!q delete [quote id]</b> | Remove a quote<br>'
        text += '<b>!q add [new quote text]</b> | Add a new quote<br>'
        text += '<b>!q search [search text]</b> | Search for a quote<br>'
        text += '<b>!q count</b> | Get total count of quotes<br>'
        text += 'React to a message with 📝 or 🔖 to save it as a quote'

        await event.respond(
            Message(
                text=text
            )
        )
