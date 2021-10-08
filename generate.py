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
import lxml.etree as ET

class Schedule:
    def __init__(self, event_id, start_date, start_time, end_date, end_time, event_form):
        self.event_id = event_id
        self.start_date = start_date
        self.start_time = start_time
        self.end_date = end_date
        self.end_time = end_time
        self.event_form = event_form # in-person or virtual


# now select timeslot that have event_id, start_time, end_time, start_date and end_date and a badge?
# interesting_timeslots = [ ts for ts in timeslots
#                           if ('event_id' in [elem.tag for elem in ts]) ] # FIXME a better way to do it is may be filter via event ids that are in mapping.xml?


# interesting_timeslots1 = [ts for ts in interesting_timeslots
#                           if 'end_date' in [elem.tag for elem in ts]]

# def schedule_from_xml(event):


class Mapping:
    def __init__(self, event_id, title):
        self.event_id = event_id
        self.title = title


def mapping_from_xml(match):
    return Mapping(match.get("event_id"), match[0].get("id"))



# print(len(schedule_xml.getroot()), len(mapping_xml.getroot()))

class Event:
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
        tmp_event_xml = ET.Element("event")
        category_xml = ET.Element("category")
        duration_xml = ET.Element("duration")
        title_xml = ET.Element("title")
        # TODO fix setters and tostring should do the job
        return lxml.etree.tostring(tmp_event)


# "SPLASH-2021-sample_demo.xml"
if __name__ == '__main__':
    print("howdy")



    mapping_xml = ET.parse("mapping.xml")
    # dictonary for event_id to confpub id mapping
    event_mappings = []
    # for match in mapping_xml.getroot():
    #     event_mapping[match.get("event_id")] = match[0].get("id")
    for match in mapping_xml.getroot():
        event_mappings.append(mapping_from_xml(match))



    schedule_xml = ET.parse("schedule.xml")
    timeslots = []
    # get all the time slots from all the subevents under events
    for c in schedule_xml.getroot():
        for cc in c:
            if cc.tag == 'timeslot':
                timeslots.append(cc)

    print(len(event_mappings), len(timeslots))
    print("bye")
