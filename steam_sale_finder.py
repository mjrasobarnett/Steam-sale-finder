#!/usr/bin/ python
# -*- coding: utf8 -*-

"""Steam Sale finder

Reads the rss feed at:
-- feed://www.steamgamesales.com/rss/?region=uk&stores=steam
and searches whether any of the games on sale match any listed in the file:
-- wanted_steam_games.txt
If there are any matches this script will post them to the twitter account:
-- @steam_sale_bot

Utilises two external packages:
-- feedparser (http://code.google.com/p/feedparser/)
-- twitter (http://mike.verdone.ca/twitter/)

"""
__author__ = u'Matt Rásó-Barnett <http://rasobarnett.com/>'

import time
import os
import re
from datetime import datetime

# Import feedparser (see: http://code.google.com/p/feedparser/)
import feedparser

# Import twitter tools (see: http://mike.verdone.ca/twitter/)
from twitter import Twitter, NoAuth, OAuth, read_token_file
from twitter.cmdline import CONSUMER_KEY, CONSUMER_SECRET
# Define where oauth key file for the twitter acoount @steam_sale_bot is located
TWITTER_OAUTH_KEY_FILE='/home/matt/.twitter_oauth_steamsalebot'
OAUTH = OAuth(*read_token_file(TWITTER_OAUTH_KEY_FILE) + (CONSUMER_KEY, CONSUMER_SECRET))
TWITTER = Twitter(domain='api.twitter.com', auth=OAUTH, api_version='1')

# Name of the RSS feed we will parse
STEAM_GAME_SALES_FEED_URL = 'feed://www.steamgamesales.com/rss/?region=uk&stores=steam'
# Name of plaintext file that lists games we will search rss feed for. The file is
# simply a list of games delimited by a new line.
REQUESTED_GAMES_FILENAME = '/home/matt/steam_sale_finder/wanted_steam_games.txt'
# Name of timestamp file which is an empty file, whose modification time is 
# always set to the current time this script is run. This is used to determine  
# which entries in the rss feed are 'new' and hence havent been checked yet
TIMESTAMP_FILENAME = '.last_update'

#_______________________________________________________________________________
def read_rss_entry_title(rss_entry_title):
   """ Parse rss entry title and return dictionary containg game_title, percent_off, price 
   
   - Expected format of the rss entry title is:
      -- NUMBER% off GAME_TITLE - Now only PRICE
   - Return a tuple containg GAME_TITLE, PERCENT_OFF, PRICE
   - Raise an exception if title does not conform to format given above 

   """
   # Define tokens, to be searched for in the title to act as delimiter for string slicing
   sale_percent_delim = "% off"
   game_title_delim = "- Now only "
   # Find position of these substrings, marking the end of the percent
   # and game_title portions of the entry
   percent_end_pos = rss_entry_title.find(sale_percent_delim)
   game_title_end_pos = rss_entry_title.find(game_title_delim)
   # Check that the format of the entry matches expectations or else exit
   if percent_end_pos == -1 or game_title_end_pos == -1:
      raise RuntimeError, "RSS entry title didn't match expected format: %s" % an_entry.title
   # Slice string to get the game title, percent discounted and price
   game_title = rss_entry_title[percent_end_pos+len(sale_percent_delim):game_title_end_pos]
   percent_off = rss_entry_title[:percent_end_pos]
   price = rss_entry_title[game_title_end_pos+len(game_title_delim):] # +1 here removes the pound sign from front of price
   # Return tuple of this information with any leading/trailing whitespace removed
   return {'game_title':game_title.strip(), 'percent_off':percent_off.strip(), 'price':price.strip()}

#_______________________________________________________________________________
def tweet_interesting_steam_sales():
   """ Read RSS feed and tweet any sales on games listed in REQUESTED_GAMES_FILENAME 
   
   This parses the RSS feed at 'STEAM_GAME_SALES_FEED_URL' and looks for any
   entries that are newer than the date that this script was last run. It
   determines this date by reading the modification date of an empty file
   defined by 'TIMESTAMP_FILENAME'. 

   Any new rss entries are then parsed by the function 'read_rss_entry_title()'
   which returns a dictionary with the parsed information.

   Then another text file, 'REQUESTED_GAMES_FILENAME', that contains a 
   (newline delimited) list of any games the user wants, is opened and this list
   of games is read into a list.

   This list of requested games is checked to see if any items are a match or 
   *sub-string* of the 'game_title' in each new rss entry. Any matches are 
   tweeted to the 

   """

   # Find the modification time of the TIMESTAMP_FILENAME as seconds since the
   # 'epoch'
   last_update_time_epoch = 0
   try:
      # Attempt to read the timestamp file's modification time
      last_update_time_epoch = os.stat(TIMESTAMP_FILENAME).st_mtime
   except OSError:
      # If no timestamp file exists, create a new file (and close it again)
      print "No timestamp file called: %s exists. Creating new one with this name." % TIMESTAMP_FILENAME
      f = open(TIMESTAMP_FILENAME, 'w+')
      f.close()

   # Convert timestamp to a datetime object in timezone=UTC
   last_update_time_utc = datetime.utcfromtimestamp(last_update_time_epoch)

   # Fetch the feed
   the_feed = feedparser.parse(STEAM_GAME_SALES_FEED_URL)
   print the_feed.feed.title
   print "Number of Entries in Feed: %d" % len(the_feed.entries)
   print "Date last checked the feed: " + last_update_time_utc.ctime()
   
   # Read in list of games we are interested in from 'REQUESTED_GAMES_FILENAME'
   requested_games = []
   try:
      with open(REQUESTED_GAMES_FILENAME,'r') as requested_games_file:
         file_data = requested_games_file.read()
         # Split file into a list of lines, using '\n' as the delimiter, 
         # and filtering out any empty lines in the process
         requested_games = [item for item in file_data.split('\n') if item != '']
   # Check that we read something from the file   
   except IOError:
      print "No requested games have been found. Check that file: %s exists or whether it is empty" % REQUESTED_GAMES_FILENAME
      return False
   
   # New entries counter
   entries_since_last_check = 0 
   # Loop over all entries in the feed
   for an_entry in the_feed.entries:
      # Find when entry was last updated
      entry_updated_time = datetime.utcfromtimestamp(time.mktime(an_entry.updated_parsed))
      # Since the list of entries is already ordered by the feed from newest to
      # oldest look down the list of entries until we reach one that is older
      # than the last_update_time
      if entry_updated_time >= last_update_time_utc:
         # Attempt to read the entry's title for offer information
         try:
            parsed_entry = read_rss_entry_title(an_entry.title)
         except RuntimeError as error:
            # If we failed to read entry, proceed to next in the list
            print error
            continue
         # Check list of requested games to see if any of these match the
         # game_title of the current rss entry. A match is if the
         # 'requested_game' string is *contained* in the 'game_title' string
         for a_requested_game in requested_games:
            if a_requested_game.lower() in parsed_entry['game_title'].lower():
               # Post to twitter timeline the matching entry's title
               TWITTER.statuses.update(status=an_entry.title)
         # Increment new entries counter
         entries_since_last_check += 1 
      else:
         break
            
   print "Number of Entries since last checked: %d" % entries_since_last_check
   # Set the modified (and access) times of the TIMESTAMP_FILENAME
   # to the current time, so that the next time this script is run it will know
   # when it was last run
   os.utime(TIMESTAMP_FILENAME, None)
   return True

#_______________________________________________________________________________
if __name__ == "__main__":
   tweet_interesting_steam_sales(
)
