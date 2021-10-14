#! /usr/local/bin/python3

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
# Optimize when # of events > 50000 and the script takes more than 1 sec.

import lxml
import csv
import datetime, dateutil
import dateutil.tz as TZ
import lxml.etree as ET
import math
from itertools import *
from enum import Enum

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
    def __init__(self, event_id, slot_id, title, room, start_ts, end_ts, is_mirror, badges, tracks, subevent, ts):
        self.event_id = event_id
        self.slot_id = slot_id
        self.title = title
        
        self.room = room
        self.start_ts = start_ts
        self.end_ts = end_ts
        self.subevent = subevent
        self.is_mirror = is_mirror
        
        self.badges = badges # in-person or virtual, keynote etc.
        self.tracks = tracks
        self.ts = ts # pointer the timeslot xml node

    def __str__(self):
        return f"Timeslot({self.title}, {self.tracks})"

    @classmethod
    def from_xml(cls, timezone, subevent, timeslot_xml):
        """
        Does validation and returns a TimeSlot Schedule
        """
        event_id = timeslot_xml.xpath(".//event_id/text()")[0]
        slot_id = timeslot_xml.xpath(".//slot_id/text()")[0]
        title = timeslot_xml.xpath(".//title/text()")[0]
        room = timeslot_xml.xpath(".//room/text()")[0]

        #annoying date/time gubbins
        start_date = timeslot_xml.xpath(".//date/text()")[0]
        start_time = timeslot_xml.xpath(".//start_time/text()")[0]
        end_date = timeslot_xml.xpath(".//end_date/text()")[0]
        end_time = timeslot_xml.xpath(".//end_time/text()")[0]

        is_mirror = False 
        mirror_els = timeslot_xml.xpath("./@is_mirror")
        if len(mirror_els) > 0:
            is_mirror = mirror_els[0] == "true"

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

        return TimeSlotSchedule(event_id, slot_id, title, room, start_ts, end_ts, is_mirror, badges, tracks, subevent, timeslot_xml)

class SubeventSchedule:
    """
    Appears as a subevent in the schedule
    <subevent>
    <subevent_id>e81627dd-cd12-4947-afc6-8153f78bd262</subevent_id>
    <title>APLAS Keynote Talks: Invited talk 1</title>
    <subevent_type type="regular"/>
    <room>Swissotel Chicago | Zurich A</room>
    <date>2021/10/17</date>
    <url>https://conf.researchr.org/track/aplas-2021/aplas-2021-keynote-talks</url>
    <url_link_display>Keynote Talks</url_link_display>
    <tracks>
        <track>Keynote Talks</track>
    </tracks>
    <timeslot/>....
    </subevent>
    """
    def __init__(self, subevent_id, title, room, tracks, timeslots):
        self.subevent_id = subevent_id
        self.title = title
        self.room = room
        self.tracks = tracks
        self.timeslots = timeslots
    @classmethod
    def from_xml(cls, timezone, subevent_xml):
        subevent_id = subevent_xml.xpath("./subevent_id/text()")[0]
        title = subevent_xml.xpath("./title/text()")[0]
        room = subevent_xml.xpath("./room/text()")[0]
        tracks = subevent_xml.xpath("./tracks/track/text()")

        ses = SubeventSchedule(subevent_id, title, room, tracks, [])
        ses.timeslots = list(map(lambda el: TimeSlotSchedule.from_xml(timezone, ses, el), subevent_xml.xpath("./timeslot[event_id]")))
        return ses

class ConferenceEvent:
    pass
class PrerecordedEvent(ConferenceEvent):
    def __init__(self, title, asset, start, duration, timeslot):
        self.title = title
        self.asset = asset
        self.start = start
        self.duration = duration
        self.timeslot = timeslot
    
    def offer_time(self, offered):
        if self.asset != None and self.asset.duration != None and self.asset.duration > self.duration:
            stretch = min(offered, self.asset.duration - self.duration)
            self.duration += stretch
            return stretch
        return datetime.timedelta()
    
    def make_playlist_element(self):
        if self.asset == None: 
            raise RuntimeError(f"Trying to generate a playlist with missing asset for {self.title} and event id {self.timeslot.event_id} in track {self.timeslot.tracks}")
        return PlaylistEvent(self.title, self.asset, "PROGRAM", self.duration, "FOLLOW", self.start, None, self.timeslot)
    
    def __str__(self):
        return f"Prerecorded({self.title}, {self.asset}, {self.start} for {self.duration}, in {self.timeslot})"
class LiveEvent(ConferenceEvent):
    def __init__(self, title, source, start, duration, timeslot, recording=None):
        assert isinstance(title, str)
        self.title = title
        self.source = source
        self.start = start
        self.duration = duration
        self.timeslot = timeslot
        self.recording = recording

    def offer_time(self, offered):
        return datetime.timedelta()
    
    def make_playlist_element(self):
        return PlaylistEvent(self.title, self.source, "LIVE", self.duration, "FOLLOW", self.start, None, self.timeslot, self.recording)
    
    def __str__(self):
        return f"Live({self.title}, {self.source}, {self.start} for {self.duration}, in {self.timeslot})"

def parse_confpub(el):
    confpub_id = el.xpath("./@id")[0]
    return f"{confpub_id}-video"
ASSET_TYPES = {
    "confpub": parse_confpub, 
    "missing": lambda el: None,
    "manual": lambda el: el.xpath("./@asset")[0]}

class PrerecordedVideo:
    def __init__(self, asset_name, duration):
        self.asset_name = asset_name
        self.duration = duration

    def __str__(self) -> str:
        return f"Prerecord({self.asset_name} for {self.duration})"
    
    def to_playlist_xml(self):
        mediaid = ET.Element("mediaid")
        mediaid.text = self.asset_name
        return "PROGRAM", mediaid
    
    def to_onsite_xml(self):
        media = ET.Element("asset")
        media.text = self.asset_name
        return media

    @classmethod
    def from_xml(cls, elem, duration_mappings):
        source = list(elem)[0]
        asset_name = ASSET_TYPES[source.tag](source)
        duration = None
        if asset_name in duration_mappings:
            duration = duration_mappings[asset_name]
        return cls(asset_name, duration)

class VideoMapping:
    def __init__(self, event_map):
        self.event_map = event_map
    def has_event(self, event_id):
        return event_id in self.event_map
    def get_event(self, event_id):
        return self.event_map[event_id]

    @classmethod
    def from_files(cls, mapping_file, asset_info):
        duration_mappings = dict()
        with open(asset_info) as csvfile:
            reader = csv.DictReader(csvfile)
            fmt = "%H:%M:%S.%f"
            for row in reader:
                dt = datetime.datetime.strptime(row["Duration"], fmt)
                duration_mappings[row["Name"]] = \
                    datetime.timedelta(hours=dt.hour, minutes=dt.minute, 
                                       seconds=dt.second, microseconds=dt.microsecond)
        mapping_xml = ET.parse(mapping_file)
        event_mappings = dict(map(lambda el: (el.xpath("./@event_id")[0], PrerecordedVideo.from_xml(el, duration_mappings)), mapping_xml.getroot()))
        return VideoMapping(event_mappings)

class EventRoom:
    def __init__(self, name, live_stream, filler_stream):
        self.name = name
        self.live = live_stream
        self.filler = filler_stream

    def remote_stream(self):
        return self.live

    def to_playlist_xml(self):
        mediaid = ET.Element("liveid")
        mediaid.text = self.live
        return "LIVE", mediaid

    def to_onsite_xml(self):
        media = ET.Element("room")
        return media

    @classmethod
    def from_xml(cls, elem):
        return cls(elem.xpath("./@name")[0], elem.xpath("./@live")[0], elem.xpath("./@filler")[0])

class ZoomInfo:
    def __init__(self, room, url, stream):
        self.room = room
        self.url = url
        self.stream = stream

    def remote_stream(self):
        return self.stream 
    
    def to_playlist_xml(self):
        mediaid = ET.Element("liveid")
        mediaid.text = self.stream
        return "LIVE", mediaid
    
    def to_onsite_xml(self):
        media = ET.Element("zoom")
        media.text = self.url
        return media

    @classmethod
    def from_xml(cls, elem):
        room_elem = elem.xpath("./@room")
        if len(room_elem) == 0:
            room = None
        else: 
            room = room_elem[0]
        return cls(room, elem.xpath("./@url")[0], elem.xpath("./@stream")[0])

# elements of an event's schedule template
class ScheduleElement:
    def make_context_dict(self, room, spec, format, timeslot):
        out = dict() 
        out['room'] = room
        out['timeslot'] = timeslot
        if spec.has_zoom():
            out['zoom'] = spec.get_zoom(room)
        return out

    def schedule(self, mapping, rooms, spec, format, timeslot, now):
        out = dict()
        if self.plenary:
            first = True
            for room in rooms:
                out_evt, new_now = self.schedule_one(mapping, room, spec, format, timeslot, now, first=first)
                out[room.name] = out_evt
                first = False
        else: 
            for room in rooms:
                previous_now = None
                if room.name == timeslot.room:
                    out_evt, new_now = self.schedule_one(mapping, room, spec, format, timeslot, now)
                    out[room.name] = out_evt
                    if new_now != previous_now and previous_now != None:
                        raise RuntimeError("Repeated scheduling of a plenary event produced a different now time")
                    elif previous_now == None:
                        previous_now = new_now
        return out, new_now

class PrerecordedElement(ScheduleElement):
    def __init__(self, source, plenary=False, backup=None):
        self.source = source
        self.plenary = plenary
        self.backup = backup

    def schedule_one(self, mapping, room, spec, format, timeslot, now, first=True):
        ctx_dict = self.make_context_dict(room, spec, format, timeslot)
        
        if not mapping.has_event(timeslot.event_id):
            raise RuntimeError(f"Playing a prerecorded video for an unmapped event ({timeslot.event_id})!")
        
        if self.source != None:
            sources = {'mirror': lambda: PrerecordedVideo(timeslot.event_id, timeslot.end_ts - timeslot.start_ts)}
            asset = sources[self.source]()
            duration = asset.duration
        else:
            asset_data = mapping.get_event(timeslot.event_id)
            if asset_data.asset_name != None:
                asset = asset_data
                duration = asset_data.duration
                    
                if duration != None and duration > (timeslot.end_ts - now):
                    duration = (timeslot.end_ts - now)
                elif duration == None and self.backup != None:
                    output = []
                    for backup in self.backup:
                        evts,now = backup.schedule(mapping, [room], spec, format, timeslot, now)
                        output.extend(evts[room.name])
                    return output, now
                elif duration == None: 
                    print(f"totally missing {timeslot.event_id}")
                    duration = (timeslot.end_ts - now)
            else:
                asset = None
                duration = (timeslot.end_ts - now)
        onairtime = now

        return [PrerecordedEvent(timeslot.title, asset, onairtime, duration, timeslot)], now+duration

    @classmethod
    def from_xml(cls, elem):
        asset = None
        source = elem.xpath('./@source')
        if len(source) > 0:
            asset = source[0]

        plenary = elem.xpath('./@plenary')
        is_plenary = len(plenary) > 0 and plenary[0] == "true"

        backup_elems = elem.xpath("./backup")
        backup_schedule = None
        if len(backup_elems) > 0:
            backup_schedule = []
            backup_elem = backup_elems[0]
            for child in backup_elem:
                if not child.tag in SCHEDULE_ELEMENT_TYPES:
                    raise RuntimeError(f"Invalid schedule element type {child.tag}")
                backup_schedule.append(SCHEDULE_ELEMENT_TYPES[child.tag].from_xml(child))

        return cls(asset, plenary=is_plenary, backup=backup_schedule)


class LiveElement(ScheduleElement): 
    def __init__(self, source, plenary=False, recording=None, xml_elem=None):
        self.source = source
        self.plenary = plenary
        self.recording = recording
        self.xml_elem = xml_elem

    def schedule_one(self, mapping, rooms, spec, format, timeslot:TimeSlotSchedule, now, first=True):
        ctx_dict = self.make_context_dict(rooms, spec, format, timeslot)
        try: 
            source = ctx_dict[self.source]
        except ValueError:
            print(f"invalid format string {self.source} in element on line {self.xml_elem.sourceline}")
            raise 
        duration = timeslot.end_ts - now
        onairtime = now
        ts = timeslot
        return [LiveEvent(timeslot.title, source, onairtime, duration, timeslot, recording=self.recording.format(**ctx_dict) if self.recording != None and first else None)], now+duration

    @classmethod
    def from_xml(cls, elem):
        source = elem.xpath('./@source')
        if len(source) == 0:
            raise RuntimeError(f"Missing source element on live; line {elem.sourceline}")

        plenary = elem.xpath('./@plenary')
        is_plenary = len(plenary) > 0 and plenary[0] == "true"

        record = elem.xpath('./@record')
        if len(record) > 0:
            recordName = record[0]
        else:
            recordName = None

        return cls(source[0], plenary=is_plenary, recording=recordName, xml_elem=elem)

class NotStreamedElement(ScheduleElement):
    def __init__(self):
        pass

    def schedule(self, mapping, rooms, spec, format, timeslot, now):
        return dict(), timeslot.end_ts
    @classmethod
    def from_xml(cls, elem):
        return cls()

SCHEDULE_ELEMENT_TYPES = dict(prerecorded=PrerecordedElement, live=LiveElement, notstreamed=NotStreamedElement)

class EventFormat:
    def __init__(self, cond, schedule, name=""):
        self.cond = cond
        self.schedules = schedule
        self.name = name

    # attempts to schedule the given timeslot with the given spec
    # if successful, returns a dict of room=>schedule elements. 
    # if did not match precondition, returns None.
    def schedule(self, scheduler, mapping, rooms, spec, timeslot):
        if not self.cond(scheduler, timeslot):
            return None

        scheduled = dict()
        now = timeslot.start_ts
        for schedule_elem in self.schedules:
            res, now = schedule_elem.schedule(mapping, rooms, spec, self, timeslot, now)
            for room, evts in res.items():
                if not room in scheduled.keys():
                    scheduled[room] = []
                scheduled[room].extend(evts)
        return scheduled

    @classmethod
    def from_xml(cls, elem):
        # =================
        # condition parsing
        # =================
        # by default we always apply
        cond = lambda sch, ts: True 
        #helper for attribute parsing
        def prop_cond(prop_xpath, if_cond, acc):
            elems = elem.xpath(prop_xpath)
            if len(elems) > 0:
                return if_cond(acc, elems[0])
            return acc
        # name condition
        cond = prop_cond("./@name", lambda cond, name: lambda sch, ts: ts.title == name and cond(sch, ts), cond)

        def is_mirror(scheduler, ts, mirrored):
            is_mirror = scheduler.is_mirror(ts)
            return scheduler.is_mirror(ts) and mirrored
        # mirror condition
        cond = prop_cond("./@mirror", lambda cond, mirrored: lambda sch, ts: (ts.is_mirror == (mirrored == "true")) and cond(sch, ts), cond)

        # badges condition
        badge_cond = elem.xpath("./@badge")
        if len(badge_cond) > 0:
            badge_req = badge_cond[0]
            old_cond = cond
            cond = lambda sch, ts: badge_req in ts.badges and old_cond(sch, ts)

        # explicit event_id condition (last minute stuff)
        event_id_cond = elem.xpath("./@event_id")
        if len(event_id_cond) >0:
            event_id_req = event_id_cond[0]
            old_cond = cond
            cond = lambda sch, ts: event_id_req == ts.event_id and old_cond(sch, ts)

        # explicit slot_id condition (last minute stuff)
        slot_id_cond = elem.xpath("./@slot_id")
        if len(slot_id_cond) >0:
            slot_id_req = slot_id_cond[0]
            old_cond = cond
            cond = lambda sch, ts: slot_id_req == ts.slot_id and old_cond(sch, ts)
            
        subevent_id_cond = elem.xpath("./@subevent_id")
        if len(subevent_id_cond) > 0:
            subevent_id_req = subevent_id_cond[0]
            old_cond = cond
            def new_cond(sch,ts):
                res_a = subevent_id_req == ts.subevent.subevent_id
                res_b = old_cond(sch, ts)
                print(f"applies to {ts.event_id}? {res_a} and {res_b}")
                return res_a and res_b
            cond = new_cond

        # ====================
        # event format parsing
        # ====================
        # mostly delegated to the elements
        # looks up the element type in SCHEDULE_ELEMENT_TYPES and calls the from_xml classmethod on it with the child
        schedule_elems = []
        for child in elem:
            if not child.tag in SCHEDULE_ELEMENT_TYPES:
                raise RuntimeError(f"Invalid schedule element type {child.tag}")
            schedule_elems.append(SCHEDULE_ELEMENT_TYPES[child.tag].from_xml(child))

        name = ""
        name_els = elem.xpath("./@format_name")
        if len(name_els) > 0:
            name = name_els[0]

        return EventFormat(cond, schedule_elems, name=name)


def merge_schedule_dicts(d1, d2):
    out = dict()
    for k1 in d1.keys():
        out[k1] = []
    for k2 in d2.keys():
        out[k2] = []
    for k1, v1 in d1.items():
        out[k1].extend(v1)
    for k2, v2 in d2.items():
        out[k2].extend(v2)
    return out

class EventSpec:
    def __init__(self, name, formats):
        self.name = name
        self.formats = formats
        self.compact_recorded = False

    def schedule(self, scheduler, mapping, rooms, subevent):
        schedule = dict()
        # TODO: compaction will break excitingly in the case of plenaries. Don't combine them.
        for ts in subevent.timeslots:
            schedule = merge_schedule_dicts(schedule, self.schedule_timeslot(scheduler, mapping, rooms, ts))
        if self.compact_recorded:
            for room, evts in schedule.items():
                now = None
                evts.sort(key=lambda evt: evt.start)
                evt = None
                offset = datetime.timedelta()
                for evt in evts:
                    if now != None:
                        offset = evt.start - now 
                        evt.start = now
                        offset -= evt.offer_time(offset)
                        now = now + evt.duration
                    else:
                        now = evt.start + evt.duration
                if evt != None:
                    evt.duration += offset
        return schedule

    def schedule_timeslot(self, scheduler, mapping, rooms, timeslot):
        for format in self.formats:
            result = format.schedule(scheduler, mapping, rooms, self, timeslot)
            if result != None:
                return result
        raise RuntimeError(f"Failure to schedule timeslot {timeslot.event_id}; formatters: {self.formats}!")
    def has_zoom(self):
        return hasattr(self, 'zoom')

    def get_zoom(self, room):
        if not self.has_zoom():
            raise RuntimeError("Tried to get the zoom instance for an event without one")
        for zoom_instance in self.zoom:
            if zoom_instance.room == None or zoom_instance.room == room.name:
                return zoom_instance
        raise RuntimeError("No zoom instance found when required!")
    @classmethod
    def from_xml(cls, elem):
        formats = list(map(EventFormat.from_xml, elem.xpath("./format")))
        out = cls(elem.xpath("./@name")[0], formats)
        zoom_elems = elem.xpath("./zoom")
        if len(zoom_elems) > 0:
            out.zoom = [ZoomInfo.from_xml(zoom_elem) for zoom_elem in zoom_elems]

        compact_recorded = elem.xpath("./@compact_recorded")
        if len(compact_recorded) > 0 and compact_recorded[0] == 'true':
            out.compact_recorded = True
        
        return out

class Scheduler:
    def __init__(self, rooms, events, main_start = None, main_end = None):
        self.rooms = rooms 
        self.events = events
        self.events_map = dict()
        self.main_start = main_start
        self.main_end = main_end
        for event_spec in self.events:
            if not event_spec.name in self.events_map:
                self.events_map[event_spec.name] = event_spec
            else:
                raise RuntimeError(f"Repeated definition of event ${event_spec.name}!")


    def schedule(self, mapping, subevent):
        scheduler = None
        for track in subevent.tracks:
            if track in self.events_map:
                scheduler = self.events_map[track]
                break
        if scheduler == None:
            raise RuntimeError(f"Was unable to find a scheduler for event {subevent.subevent_id} in tracks {subevent.tracks}!")
        return scheduler.schedule(self, mapping, self.rooms, subevent)

    @classmethod
    def from_xml(cls, elem):
        mirroring_els = elem.xpath("./mirroring")
        main_start = None
        main_end = None
        if len(mirroring_els) > 0:
            mirroring_el = mirroring_els[0]
            # find when the main track starts and ends
            tz = TZ.gettz(mirroring_el.xpath("./@timezone")[0])
            main_start = datetime.time.fromisoformat(mirroring_el.xpath("./@start")[0]).replace(tzinfo=tz)
            main_end = datetime.time.fromisoformat(mirroring_el.xpath("./@end")[0]).replace(tzinfo=tz)
        rooms = list(map(EventRoom.from_xml, elem.xpath(".//rooms/room")))
        events = list(map(EventSpec.from_xml, elem.xpath(".//events/event")))
        return cls(rooms, events, main_start, main_end)


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
    def __init__(self, title, source, category, duration, endmode, onairtime, m, ts, recording=None):
        assert isinstance(title, str)
        self.title = title
        self.source = source
        self.category = category
        self.duration = duration
        self.endmode = endmode
        self.onairtime = onairtime
        self.recording = recording

        self.m = m
        self.ts = ts

    def __str__(self):
        return f"PlaylistEvent({self.title}; {self.onairtime} for {self.duration}; for {self.ts})"

    def to_session_chair_xml(self):
        event = ET.Element("event")
        event.set("title", self.title)
        event.set("start", self.onairtime.isoformat())
        event.set("nominal_start", self.ts.start_ts.isoformat())
        event.set("duration", str(self.duration.total_seconds()))
        event.set("nominal_duration", str(self.ts.end_ts - self.ts.start_ts))
        event.set("session", self.ts.subevent.title)

        tracks = ET.Element("tracks")
        event.append(tracks)
        for track in self.ts.tracks:
            track_el = ET.Element("track")
            track_el.text = track
            tracks.append(track_el)
        
        event.append(self.source.to_onsite_xml())
        return event

    def to_xml(self):
        """
        This returns the etree object
        """
        # The base element
        event = ET.Element("event")


        duration = ET.Element("duration")
        total_secs = self.duration.total_seconds()
        hours,remainder = divmod(total_secs, 60*60)
        minutes,remainder = divmod(remainder, 60)
        seconds,fractional_seconds = divmod(remainder, 1)
        frames = math.floor(fractional_seconds*25)
        duration.text = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}:{int(frames):02d}"
        
        
        title = ET.Element("title")
        title.text = self.title
        if not self.title:
            print(f"Warning: {self.ts.event_id} has an empty title")

        category_type, idel = self.source.to_playlist_xml() 
        category = ET.Element("category")
        category.text = category_type

        onairtime = ET.Element("onairtime")
        onairtime.text = self.onairtime.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S:00")
        recordingpat = ET.Element("recordingPattern")
        recordingpat.text = self.recording if self.recording != None else "" # TODO: what is this, how is it computed
                                       # I am guessing it is be the confpub id value from the mapping xml?
        # Bunch of defaults
        offset = ET.Element("offset")
        offset.text = "00:00:00:00"
        endmode = ET.Element("endmode")
        endmode.text = "FOLLOW"
        igincomsig = ET.Element("ignoreincomingscte35signals")
        igincomsig.text = "false"

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
        
        
        playoutswithlist = ET.Element("playoutswitchlist")
        recording = ET.Element("recording") # TODO: Confirm! if category is not live then we dont have to record,
                                            # or do we record everything or there are some events that we won't record?
        recording.text = "true" if self.recording != None else "false"

        
        event.extend (
              [ category, title, duration, onairtime, idel, recordingpat ]
            + [ offset, endmode, igincomsig, maxExtendedDuration, scte35list
                , som, playoutswithlist, startmode, recording
                , twitchrpclist, untimedAdList, voiceoverlist ]
        )
        
        return event


def gen_playlist_event(m, ts):
    """
    Given a event mapping and a schedule timeslot generates a playlist event
    """    
    title = m.title
    category = "LIVE" # FIXME
    duration = ts.end_ts - ts.start_ts
    endmode = "FOLLOW" # TODO: Confirm this
    onairtime = ts.start_ts
        
    return PlaylistEvent(title, category, duration, endmode, onairtime, m, ts)


def window(iterable, size):
    """
    sliding window over an iterable
    src: https://stackoverflow.com/questions/6822725/rolling-or-sliding-window-iterator 
    """
    iters = tee(iterable, size)
    for i in range(1, size):
        for each in iters[i:]:
            next(each, None)
    return list(zip(*iters))

def gen_fillers(room_id, timeslots):
    """
    Takes a list of time ordered timeslot if any two events have a gap then we generate a filler event to fit in the gap
    """
    adjacent_ts = list(window(timeslots, 2))
    fillers = []
    for (e1, e2) in adjacent_ts:
        if e2.onairtime < e1.onairtime + e1.duration:
            print(f"Warning: Overlapping events {e1.ts.title} {e2.ts.title}")
        if e2.onairtime > e1.onairtime + e1.duration: # TODO may be the diff should be between a threshold?
            print(f"We have a {str(e2.onairtime - (e1.onairtime + e1.duration))} hr gap between {e1.title} and {e2.title}")
            fillers.append(PlaylistEvent("FILLER_"+room_id
                                         , "LIVE" # TODO Fillers won't be live... ?
                                         , e2.onairtime - (e1.onairtime + e1.duration)
                                         , e1.endmode
                                         , e1.onairtime + e1.duration, # start after the prev event ends
                                         None, # We don't have a mapping or timeslot xml object for fillers
                                         None))
    return fillers
        

    
def gen_playlist(room_id, event_mappings, timeslots_mappings):
    """
    Given an map of event mappings and a map of event schedules generates a playlist 
    """
    event_ids = event_mappings.keys() & timeslots_mappings.keys()
    
    es = map(lambda x: gen_playlist_event(event_mappings[x], timeslots_mappings[x]), event_ids)

    pl = sorted(es, key=lambda x: x.onairtime)

    fillers = gen_fillers(room_id, pl)

    return list(sorted ((pl + fillers), key=lambda x: x.onairtime))
        
    
def validate_playlist(pl):
    """
    For a room, we don't want multiple events running or 
    two adjacent events overlap each other.
    """
    sorted_pl = sorted(pl, key=lambda x: x.onairtime)
    adj_evs = list(window(sorted_pl, 2))
    for (e1, e2) in adj_evs:
        if e2.onairtime < e1.onairtime + e1.duration:
            print(f"{e1.title} ({e1.ts.event_id}@{e1.onairtime}-{e1.duration.total_seconds()}) runs over {e2.title} ({e2.ts.event_id}@{e2.onairtime}-{e2.duration.total_seconds()}) by {((e1.onairtime + e1.duration) - e2.onairtime).total_seconds()}")

def make_chair_xml(in_room, schedule_xml, scheduler):
    room = ET.Element("room")
    if scheduler.main_start != None and scheduler.main_end != None:
        room.set("main_start", scheduler.main_start.isoformat())
        room.set("main_end", scheduler.main_end.isoformat())
    room.set("timezone", schedule_xml.xpath("//timezone_id/text()")[0])
    room.set("room", in_room)
    return room

# prduces 3 files "SPLASH-2021-playlist-demo-Zurich{A|B|C}.xml"
if __name__ == '__main__':
    print("howdy")
    
    base_output_file = "SPLASH21-playlist-demo-Zurich-" # FIXME remove demo for final
    base_room = "Swissotel Chicago | Zurich "

    room_ids = ["A", "B", "C"]
    
    rooms = [base_room + r for r in room_ids]


    schedule_xml = ET.parse("schedule.xml")

    schedule_timezone = TZ.gettz(schedule_xml.xpath("//timezone_id/text()")[0])

    print(f"for timezone {schedule_timezone}")

    subevents = list(map(lambda el: SubeventSchedule.from_xml(schedule_timezone, el), schedule_xml.xpath("//subevent[subevent_id]")))

    mapping = VideoMapping.from_files("mapping.xml", "asset-info.csv")
    parser = ET.XMLParser(remove_comments=True)
    scheduler = Scheduler.from_xml(ET.parse("liveinfo.xml", parser = parser))

    schedule = dict()
    for se in subevents:
        if not se.room in rooms:
            continue
        schedule = merge_schedule_dicts(schedule, scheduler.schedule(mapping, se))
    
    room_playlists = dict()
    for room, evts in schedule.items():
        evts.sort(key=lambda evt: evt.start)
        room_playlists[room] = list(map(lambda evt: evt.make_playlist_element(), evts))
        print(f"validating playlist for room {room}")
        validate_playlist(room_playlists[room])
        
    # TODO: insert filler elements
    for r in room_ids:
        current_room = base_room + r
        print(f"Generating Playlist for {current_room}")
        # a single event_id can appear more than once 
        # (they're duplicated for mirrored events)
        # so we can't build a map based on them. Only slot_ids are unique.
        
        # generate playlist for a room    
        root = ET.Element("playlist")
        
        listmeta = ET.Element("list")
        name = ET.Element("name")
        name.text = current_room
        listmeta.append(name)
        root.append(listmeta)

        eventlist = ET.Element("eventlist")
        eventlist.set("timeinmilliseconds", "true")
        root.append(eventlist)
        playlist_xml = map (PlaylistEvent.to_xml, filter(lambda evt: evt.duration.total_seconds() > 0, room_playlists[current_room]))
        eventlist.extend(list(playlist_xml))
        
        chair_root_xml = make_chair_xml(room, schedule_xml, scheduler)
        session_chair_xml = map(PlaylistEvent.to_session_chair_xml, filter(lambda evt: evt.duration.total_seconds() > 0, room_playlists[current_room])) 
        chair_root_xml.extend(list(session_chair_xml))

        # write it to a file
        output_file = base_output_file + r + ".xml"
        print(f"writing to file {output_file}")
        with open(output_file, "wb") as xf:
            xf.write(ET.tostring(root, pretty_print=True, xml_declaration=True, encoding='utf-8', standalone=True))

        output_session_chair_file = base_output_file + r + "_chair.xml"
        print(f"writing to file {output_session_chair_file}")
        with open(output_session_chair_file, "wb") as xf:
            xf.write(ET.tostring(chair_root_xml, pretty_print=True, xml_declaration=True, encoding='utf-8', standalone=True))
        
        
    # TODO: find filler events in the timeline
    # TODO: Some manual events whose durations we don't know, cut through filler or zoom room (ANI: I don't undrstand this)
    # TODO: maybe take file names are arguments to the script.
    
    print("bye")
