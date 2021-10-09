#! /usr/bin/python3

# We have two input files
# 1. Schedule from researchr.conf called schedule.xml
#    - This contains
#        <events>
#           <subevents>
#              <timeslot>
#              
# 2. Mapping file that maps event ids to confpub id
#
# We need to output a file that has the following structure:
# - <playlist>
#     <eventlist timeinmilliseconds="false">
#        <event>
#         ...
#        </event>

import lxml
import datetime, dateutil
import dateutil.tz as TZ
import lxml.etree as ET


class TimeSlotSchedule:
    """
    Appears as a timeslot in the schedule
    <timeslot>
      <slot_id>db0c516c-2586-43e1-be4d-958a3b92057a</slot_id>
      <event_id>754ed478-9409-48b7-a054-dd3a25f7d775</event_id>
      <title>Invited Speaker</title>
      <room>Swissotel Chicago | Zurich C</room>
      <date>2021/10/19</date>
      <start_time>18:20</start_time>
      <end_date>2021/10/19</end_date>
      <end_time>18:50</end_time>
      <description>undefined</description>
      <persons>...</persons>
      <tracks>
        <track>Ask Me Anything (AMA)</track>
      </tracks>
      <badges>
        <badge>AMA</badge>
        <badge property="Event Form">Virtual</badge>
      </badges>
    </timeslot>
    """
    def __init__(self, event_id, room, start_ts, end_ts, badges, tracks, ts):
        self.event_id = event_id
        self.room = room
        self.start_ts = start_ts
        self.end_ts = end_ts

        self.badges = badges # in-person or virtual, keynote etc.
        self.tracks = tracks

        self.ts = ts # pointer the timeslot xml node

    def from_xml(timezone, timeslot_xml):
        """
        Does validation and returns a TimeSlot Schedule
        """
        event_id = timeslot_xml.xpath(".//event_id/text()")[0]
        title = timeslot_xml.xpath(".//title/text()")[0]
        room = timeslot_xml.xpath(".//room/text()")[0]

        #annoying date/time gubbins
        start_date = timeslot_xml.xpath(".//date/text()")[0]
        start_time = timeslot_xml.xpath(".//start_time/text()")[0]
        end_date = timeslot_xml.xpath(".//end_date/text()")[0]
        end_time = timeslot_xml.xpath(".//end_time/text()")[0]

        researchr_fstring = "%Y/%m/%d %H:%M"
        start_ts = datetime.datetime.strptime(f"{start_date} {start_time}", researchr_fstring).replace(tzinfo=timezone)
        end_ts = datetime.datetime.strptime(f"{end_date} {end_time}", researchr_fstring).replace(tzinfo=timezone)

        # description and persons elided; we don't need them for scheduling

        # track information
        tracks = timeslot_xml.xpath(".//tracks/track/text()")

        # badges information
        # badges are annoying. Some of them have a "property" (really only the Event Form ones), while most don't
        # however, basically all of them have some semantic use. Keynotes, for example, are (sometimes) plenary, etc
        # for now we'll just shove them into an array without including the property data
        # ANI: Maybe we can have a class Badge to define that behaviour
        badges = timeslot_xml.xpath(".//badges/badge/text()")

        return TimeSlotSchedule(event_id, room, start_ts, end_ts, badges, tracks, timeslot_xml)
        

class Mapping:
    def __init__(self, event_id, title, m):
        self.event_id = event_id
        self.title = title

        self.m = m # pointer to the mapping xml node

        

def mapping_from_xml(match):
    """
    A sample mapper
    <match event_id="2b702965-d312-4316-8d55-39a1e0d157f4">
        <confpub id="splashws21slemain-p44-p"/>
    </match>
    """
    return Mapping(match.get("event_id"), match[0].get("id"), match)

# # ANI: I am going to merge your way of doing it with  mine.
# # The reason being I want to keep the validation layer separate from the object creation.
# # But I like the way you use xpaths.
# class Timeslot:
#     """
#     An example timeslot
#     <timeslot>
#       <slot_id>1b9393da-cc9d-4307-98e8-03dd6215eb94</slot_id>
#       <event_id>c37258b4-1df6-476e-b6e1-b5168f6b0ece</event_id>
#       <submission_id>32</submission_id>
#       <title>Synbit: Synthesizing Bidirectional Programs using Unidirectional Sketches</title>
#       <room>Swissotel Chicago | Zurich A</room>
#       <date>2021/10/20</date>
#       <start_time>19:35</start_time>
#       <end_date>2021/10/20</end_date>
#       <end_time>19:50</end_time>
#       <description></description>
#       <persons> [...]
#       </persons>
#       <tracks>
#         <track>OOPSLA</track>
#       </tracks>
#       <badges>
#         <badge property="Event Form">Virtual</badge>
#       </badges>
#     </timeslot>
#     """
#     def __init__(self, timezone, timeslot_xml):
#         #basic metadata
#         self.event_id = timeslot_xml.xpath(".//event_id/text()")[0]
#         self.title = timeslot_xml.xpath(".//title/text()")[0]
#         self.room = timeslot_xml.xpath(".//room/text()")[0]

#         #annoying date/time gubbins
#         start_date = timeslot_xml.xpath(".//date/text()")[0]
#         start_time = timeslot_xml.xpath(".//start_time/text()")[0]
#         end_date = timeslot_xml.xpath(".//end_date/text()")[0]
#         end_time = timeslot_xml.xpath(".//end_time/text()")[0]

#         researchr_fstring = "%Y/%m/%d %H:%M"
#         self.start = datetime.datetime.strptime(f"{start_date} {start_time}", researchr_fstring).replace(tzinfo=timezone)
#         self.end = datetime.datetime.strptime(f"{end_date} {end_time}", researchr_fstring).replace(tzinfo=timezone)

#         # description and persons elided; we don't need them for scheduling

#         # track information
#         self.tracks = timeslot_xml.xpath(".//tracks/track/text()")

#         # badges information
#         # badges are annoying. Some of them have a "property" (really only the Event Form ones), while most don't
#         # however, basically all of them have some semantic use. Keynotes, for example, are (sometimes) plenary, etc
#         # for now we'll just shove them into an array without including the property data
#         self.badges = timeslot_xml.xpath(".//badges/badge/text()")


class PlaylistEvent:
    """
    An example event
      <event>
         <category>LIVE</category>
         <duration>00:15:00:00</duration>
         <endmode>FOLLOW</endmode>
         <ignoreincomingscte35signals>false</ignoreincomingscte35signals>
         <maxExtendedDuration>00:00:00:00</maxExtendedDuration>
         <offset>00:00:00:00</offset>
         <onairtime>2021-09-20T21:01:59:13</onairtime>
         <playoutswitchlist/>
         <recording>false</recording>
         <recordingPattern>$(title)</recordingPattern>
         <scte35list/>
         <secondaryeventlist/>
         <som>00:00:00:00</som>
         <startmode>FOLLOW</startmode>
         <title>live-demo</title>
         <twitchrpclist/>
         <untimedAdList/>
         <voiceoverlist/>
      </event>
    """
    def __init__(self, title, category, duration, endmode, onairtime):
        self.title = title
        self.category = category
        self.duration = duration
        self.endmode = endmode
        self.onairtime = onairtime



    def to_xml(self):
        """
        This returns the etree object
        """
        # The base element
        event = ET.Element("event")

        category = ET.Element("category")
        category.text = self.category

        duration = ET.Element("duration")
        duration.text = str(self.duration)
        
        title = ET.Element("title")
        title.text = self.title

        onairtime = ET.Element("onairtime")
        onairtime.text = str(self.onairtime)

        recordingpat = ET.Element("recordingpattern")
        recordingpat.text = "$(title)" # TODO: what is this, how is it computed?
                                       # I think it should be the confpub id value from the mapping xml?
        # Bunch of defaults
        offset = ET.Element("offset")
        offset.text = "00:00:00:00"
        endmode = ET.Element("endmode")
        endmode.text = "FOLLOW"
        igincomsig = ET.Element("ignoreincomingscte35signals")
        igincomsig_text = "false"

        maxExtendedDuration = ET.Element("maxExtendedDuration")
        maxExtendedDuration.text = "00:00:00:00"

        scte35list = ET.Element("scte35list")
        secondaryeventlist = ET.Element("secondaryeventlist")

        som = ET.Element("som")
        som.text = "00:00:00:00"
        
        startmode = ET.Element("startmode") ## TODO: I am assuming this is default
        startmode.text = "FOLLOW"

        twitchrpclist = ET.Element("twitchrpclist")
        untimedAdList = ET.Element("untimedAdList")
        voiceoverlist = ET.Element("voiceoverlist")
        
        
        playoutswithlist = ET.Element("playoutswithlist")
        recording = ET.Element("recording") # TODO: Confirm! if category is not live then we dont have to record,
                                            # or do we record everything or there are some events that we won't record?
        recording.text = "true"

        
        event.extend (
              [ category, title, duration ]
            + [ offset, endmode, igincomsig, maxExtendedDuration, scte35list
              , som, startmode, twitchrpclist, untimedAdList, voiceoverlist ]
        )
        
        return event # ideally we'd like to have a pretty printer. but thats not necessary right now.


def generate_playlist(event_mappings, timeslots_mappings):
    # first get the common keyset
    interesting_event_ids = event_mappings.keys() & timeslots_mappings.keys()
    # Why are there just 72 of them?

    es = []
    for k in interesting_event_ids:
        m = event_mappings[k]
        ts = timeslots_mappings[k]
        
        title = m.title
        category = "LIVE" # FIXME
        duration = ts.end_ts - ts.start_ts
        endmode = "FOLLOW" # Confirm
        onairtime = ts.start_ts # TODO: I believe ideally we need to arrange this in an ascending order
                                 #      so that we can find filler events
        
        es.append(
            PlaylistEvent(title, category, duration, endmode, onairtime)
        )

    return es

    
# prduces 3 files "SPLASH-2021-playlist-Zurich{A|B|C}.xml"
if __name__ == '__main__':
    print("howdy")
    base_output_file = "SPLASH21-playlist-demo-Zurich-" # FIXME remove demo for final
    base_room = "Swissotel Chicago | Zurich "
    roomA = base_room + "A"
    room_ids = ["A", "B", "C"]
    
    rooms = [base_room + r for r in room_ids]

    mapping_xml = ET.parse("mapping.xml")
    # dictonary for event_id to confpub id mapping
    event_mappings = {}
    # for match in mapping_xml.getroot():
    #     event_mapping[match.get("event_id")] = match[0].get("id")
    for match in mapping_xml.getroot():
        m = mapping_from_xml(match)
        event_mappings[m.event_id] = m


    schedule_xml = ET.parse("schedule.xml")

    schedule_timezone = TZ.gettz(schedule_xml.xpath("//timezone_id/text()")[0])

    print(f"for timezone {schedule_timezone}")

    # get all the time slots from all the subevents under events
    timeslots_xml = schedule_xml.getroot().xpath("//timeslot[event_id]")
    # for ts in schedule_xml.getroot().xpath("//timeslot[event_id]"):
        # timeslots.append(Timeslot(schedule_timezone, ts))
        # timeslots.append(ts)

    # timeslots_to_schedule = list(filter(lambda x: x.room == roomA, timeslots))
    # timeslots = []
    # for c in schedule_xml.getroot():
    #     for cc in c:
    #         if cc.tag == 'timeslot':
    #             timeslots.append(cc)

    # we filter on only those timeslots that have an event_id and a badges node
    timeslots = []
    for ts in timeslots_xml:
        elems = [c.tag for c in ts] # TODO use xpath maybe?
        if "badges" in elems:
            timeslots.append(TimeSlotSchedule.from_xml(schedule_timezone, ts))

    print(f"Parsed Schedule({len(timeslots)}) and event mappings({len(event_mappings)})")
            
    # No one cares about efficiency when we have < 5000 elements.
    for r in room_ids:
        print(f"scheduling for {base_room + r}")
        output_file = base_output_file + r + ".xml"

        # mapping between even_ids and schedule timeslots
        timeslots_mapping = {}
        for ts in timeslots:
            if ts.room == base_room + r:
                timeslots_mapping[ts.event_id] = ts
        
        # generate playlist for a room    
        print(f"writing to file {output_file}")
        # write it to a file
        root = ET.Element("playlist")
        eventlist = ET.Element("eventlist")
        eventlist.set("timeinmilliseconds", "false")
        root.append(eventlist)
        
        playlist_xml = map (PlaylistEvent.to_xml, generate_playlist(event_mappings, timeslots_mapping))
        root.extend(list(playlist_xml))
        
        with ET.xmlfile(output_file, encoding='utf-8', close=True) as xf:
            xf.write(root) # TODO add metadata <?xml version="1.0" encoding=... >
        
    # TODO: find filler events in the timeline
    # TODO: Some manual events whose durations we don't know, cut through filler or zoom room (ANI: I don't undrstand this)
    
    print("bye")
