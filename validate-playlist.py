#! /usr/local/bin/python3

# We have multiple playlists files (one for each room) that we have generated from
# the big horrible ad-hoc mess of schedule and mapping and what not xml/cvs files 

# We want to validate that the playlist is valid with these characteristics:
# - No events overlap
# - The events don't run over the assigned stream time.
# - There are no gaps in the playlist (This is needed for making sure the stream doesn't die)
# - don't replay prerecords that haven't happened yet

import math
from itertools import *

import lxml
# import csv
# import datetime, dateutil
# import dateutil.tz as TZ
import lxml.etree as ET

import importlib.machinery
import importlib.util

# Import gen-playlist
loader = importlib.machinery.SourceFileLoader( 'gen-playlist.py', './gen-playlist.py' )
spec = importlib.util.spec_from_loader( 'gen-playlist.py', loader )
gpl = importlib.util.module_from_spec( spec )
loader.exec_module( gpl )

def validate_adjacent_events(pl):
    """
    For a room, we don't want multiple events running or 
    two adjacent events overlap each other.
    """
    print("Making sure there are no over runs on adjacent events")
    sorted_pl = sorted(pl, key=lambda x: x.onairtime)
    adj_evs = list(gpl.window(sorted_pl, 2))
    for (e1, e2) in adj_evs:
        if e2.onairtime < e1.onairtime + e1.duration:
            print(f"Warning: {e1.title} ({e1.onairtime}-{e1.duration.total_seconds()})\n"
                  + f"runs over {e2.title} ({e2.onairtime}-{e2.duration.total_seconds()})\n"
                  + f"by {((e1.onairtime + e1.duration) - e2.onairtime).total_seconds()} secs")
    return pl


def find_duplicates(sequence):
    """
    source: https://www.iditect.com/guide/python/python_howto_find_the_duplicates_in_a_list.html
    """
    first_seen = set()
    first_seen_add = first_seen.add  
    duplicates = set(i for i in sequence if i in first_seen or first_seen_add(i) )
    # turn the set into a list (as requested)
    return duplicates 
            
def recording_pattern_is_unique(pl):
    """
    Make sure there is only one recording pattern for an event
    We have mirrors and only the first event should be LIVE, the other event should be PROGRAM
    """
    print("Making sure there are no duplicate recordingPatterns")
    # print(len(list(pl)))
    
    reps = list(map( lambda e: e.recordingPat
                   , filter(lambda e: e.recordingPat != None
                            , pl)))
    #  print(list(map(lambda e: e.recordingPat, pl)))
    dups = find_duplicates(reps)
    if len(dups) > 1:
        print(f"Warning: Found duplicate record patterns {dups}")
    
            
def validate_playlist(pl):

    validate_adjacent_events(pl)

    recording_pattern_is_unique(pl)

            

if __name__ == "__main__":
    for r in gpl.room_ids:
        file_for_room = gpl.base_output_file + r + ".xml"
    
        pl_xml = ET.parse(file_for_room)
    
        pl_events = list(map(gpl.PlaylistEvent.from_xml, pl_xml.xpath("/playlist/eventlist/event")))

        print(f"loaded {len(pl_events)} events from {file_for_room} for validation")

        validate_playlist(pl_events)
        
        print(f"validation done")

        
    
