#! /usr/local/bin/python3

# We have multiple playlists files (one for each room) that we have generated from
# the big horrible ad-hoc mess of schedule and mapping and what not xml/cvs files 

# We want to validate that the playlist is valid with these characteristics:
# - No events overlap
# - The events don't run over the assigned stream time.
# - There are no gaps in the playlist (This is needed for making sure the stream doesn't die)

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


def validate_playlist(pl):
    """
    For a room, we don't want multiple events running or 
    two adjacent events overlap each other.
    """
    sorted_pl = sorted(pl, key=lambda x: x.onairtime)
    adj_evs = list(gpl.window(sorted_pl, 2))
    for (e1, e2) in adj_evs:
        if e2.onairtime < e1.onairtime + e1.duration:
            print(f"Warning: {e1.title} ({e1.onairtime}-{e1.duration.total_seconds()})\n"
                  + f"runs over {e2.title} ({e2.onairtime}-{e2.duration.total_seconds()})\n"
                  + f"by {((e1.onairtime + e1.duration) - e2.onairtime).total_seconds()}")


            

if __name__ == "__main__":
    print("Starting Validation for")

    for r in gpl.room_ids:
        file_for_room = gpl.base_output_file + r + ".xml"
    
        pl_xml = ET.parse(file_for_room)
    
        pl_events = map(gpl.PlaylistEvent.from_xml, pl_xml.xpath("/playlist/eventlist/event"))

        print(f"loaded events from {file_for_room}")
    
        validate_playlist(pl_events)
    

    
    
