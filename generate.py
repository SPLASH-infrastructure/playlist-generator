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
    def __init__(self, event_id, start_date, start_time, end_date, end_time, badge_event_form):
        self.event_id = event_id
        self.start_date = start_date
        self.start_time = start_time
        self.end_date = end_date
        self.end_time = end_time
        self.badge_event_form = badge_event_form # in-person or virtual



class Mapping:
    def __init__(self, event_id, title):
        self.event_id = event_id
        self.title = title


def mapping_from_xml(match):
    """
    A sample mapper
    <match event_id="2b702965-d312-4316-8d55-39a1e0d157f4">
        <confpub id="splashws21slemain-p44-p"/>
    </match>
    """
    return Mapping(match.get("event_id"), match[0].get("id"))

class Timeslot:
    """
    An example timeslot
    <timeslot>
      <slot_id>1b9393da-cc9d-4307-98e8-03dd6215eb94</slot_id>
      <event_id>c37258b4-1df6-476e-b6e1-b5168f6b0ece</event_id>
      <submission_id>32</submission_id>
      <title>Synbit: Synthesizing Bidirectional Programs using Unidirectional Sketches</title>
      <room>Swissotel Chicago | Zurich A</room>
      <date>2021/10/20</date>
      <start_time>19:35</start_time>
      <end_date>2021/10/20</end_date>
      <end_time>19:50</end_time>
      <description></description>
      <persons> [...]
      </persons>
      <tracks>
        <track>OOPSLA</track>
      </tracks>
      <badges>
        <badge property="Event Form">Virtual</badge>
      </badges>
    </timeslot>
    """
    def __init__(self, timezone, timeslot_xml):
        #basic metadata
        self.event_id = timeslot_xml.xpath(".//event_id/text()")[0]
        self.title = timeslot_xml.xpath(".//title/text()")[0]
        self.room = timeslot_xml.xpath(".//room/text()")[0]

        #annoying date/time gubbins
        start_date = timeslot_xml.xpath(".//date/text()")[0]
        start_time = timeslot_xml.xpath(".//start_time/text()")[0]
        end_date = timeslot_xml.xpath(".//end_date/text()")[0]
        end_time = timeslot_xml.xpath(".//end_time/text()")[0]

        researchr_fstring = "%Y/%m/%d %H:%M"
        self.start = datetime.datetime.strptime(f"{start_date} {start_time}", researchr_fstring).replace(tzinfo=timezone)
        self.end = datetime.datetime.strptime(f"{end_date} {end_time}", researchr_fstring).replace(tzinfo=timezone)

        # description and persons elided; we don't need them for scheduling

        # track information
        self.tracks = timeslot_xml.xpath(".//tracks/track/text()")

        # badges information
        # badges are annoying. Some of them have a "property" (really only the Event Form ones), while most don't
        # however, basically all of them have some semantic use. Keynotes, for example, are (sometimes) plenary, etc
        # for now we'll just shove them into an array without including the property data
        self.badges = timeslot_xml.xpath(".//badges/badge/text()")


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
    def __init__(self, title, category, duration, endmode
                 , maxExtendedDuration, offset, onairtime):
        self.category = category
        self.duration = duration
        self.endmode = endmode
        self.onairtime = onairtime
        self.title = title


    def to_xml(self):
        tmp_event_n = ET.Element("event")
        category_n = ET.Element("category")
        category_n.text = self.category
        
        duration_n = ET.Element("duration")
        duration_n.text = self.duration
        
        title_n = ET.Element("title")
        
        # Bunch of defaults
        offset_n = ET.Element("offset")
        offset_n.text = "00:00:00:00"
        endmode_n = ET.Element("endmode")
        endmode_n.text = "FOLLOW"
        igincomsig_n = ET.Element("ignoreincomingscte35signals")
        endmode_n.text = "false"
        # TODO fix setters and tostring should do the job
        return lxml.etree.tostring(tmp_event_n)


# "SPLASH-2021-sample_demo.xml"
if __name__ == '__main__':
    print("howdy")



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
    # get all the time slots from all the subevents under events
    timeslots = []
    for ts in schedule_xml.getroot().xpath("//timeslot[event_id]"):
        timeslots.append(Timeslot(schedule_timezone, ts))
    
    timeslots = []
    for c in schedule_xml.getroot():
        for cc in c:
            if cc.tag == 'timeslot':
                timeslots.append(cc)

    # mapping between even_ids and schedule timeslots
    # we filter on only those timeslots that have an event_id and a badges node
    timeslots1 = []
    for ts in timeslots:
        elems = [c.tag for c in ts]
        if "event_id" in elems and "badges" in elems:
            timeslots1.append(ts)

    timeslots_mapping = {}
    for ts in timeslots1:
        timeslots_mapping[ts.find("event_id").text] = TimeSlotSchedule(ts.find("event_id").text
                                                                       , "" # ts.find("start_date").text
                                                                       , ts.find("start_time").text
                                                                       , ts.find("end_date").text
                                                                       , ts.find("end_time").text
                                                                       , "FixBadges")
        
    
    print(len(event_mappings), len(timeslots1))
    
    
    
    print("bye")
