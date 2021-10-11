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
from itertools import *


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
    def __init__(self, event_id, title, room, start_ts, end_ts, badges, tracks, ts):
        self.event_id = event_id
        self.title = title
        
        self.room = room
        self.start_ts = start_ts
        self.end_ts = end_ts
        
        self.badges = badges # in-person or virtual, keynote etc.
        self.tracks = tracks
        self.ts = ts # pointer the timeslot xml node

    def __str__(self):
    	return f"Timeslot({self.title}, {self.tracks})"
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

        return TimeSlotSchedule(event_id, title, room, start_ts, end_ts, badges, tracks, timeslot_xml)
        
class PrerecordedVideo:
    def __init__(self, event_id, title, m):
        self.event_id = event_id
        self.title = title
        self.m = m # pointer to the mapping xml node

    @classmethod
    def mapping_from_xml(cls, match):
        """
        A sample mapper
        <match event_id="2b702965-d312-4316-8d55-39a1e0d157f4">
            <confpub id="splashws21slemain-p44-p"/>
        </match>
        """
        return cls(match.get("event_id"), match[0].get("id"), match)

class EventRoom:
    def __init__(self, name, livestream=None):
        self.name = name
        self.livestream = livestream
    @classmethod
    def from_xml(cls, xml_elem):
        pass # for now

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
    def __init__(self, title, category, duration, endmode, onairtime, m, ts):
        self.title = title
        self.category = category
        self.duration = duration
        self.endmode = endmode
        self.onairtime = onairtime

        self.m = m
        self.ts = ts

    def __str__(self):
    	return f"PlaylistEvent({self.title}; {self.onairtime} for {self.duration}; for {self.ts})"

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
        if not self.title:
            print(f"Warning: {self.ts.event_id} has an empty title")

        onairtime = ET.Element("onairtime")
        onairtime.text = self.onairtime.isoformat(timespec='seconds')

        recordingpat = ET.Element("recordingpattern")
        recordingpat.text = "$(title)" # TODO: what is this, how is it computed
                                       # I am guessing it is be the confpub id value from the mapping xml?
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
              [ category, title, duration, onairtime, recordingpat ]
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
    filler_threshold = (1, 2) # generate a filler only if the gap is between this duration.
    
    adjacent_ts = list(window(timeslots, 2))
    fillers = []
    for (e1, e2) in adjacent_ts:
        if e2.onairtime < e1.onairtime + e1.duration:
            print(f"Warning: Overlapping events {e1.ts.title} {e2.ts.title}")
        if e2.onairtime > e1.onairtime + e1.duration: # TODO may be the diff should be between a threshold?
            print(f"We have a {str(e2.onairtime - (e1.onairtime + e1.duration))} hr gap between {e1.title} and {e2.title}")
            fillers.append(PlaylistEvent("FILLER_"+room_id
                                         , "FILLER" # TODO Fillers won't be live... ?
                                         , e2.onairtime - (e1.onairtime + e1.duration)
                                         , e1.endmode
                                         , e1.onairtime + e1.duration, # start after the prev event ends
                                         None, # We don't have a mapping or timeslot xml object for fillers
                                         None))
    return fillers

class VideoMapping:
	def __init__(self, asset_map, duration_map):
		self.asset_map = asset_map
		self.duration_map = duration_map
	def has_event(self, event_id):
		return event_id in self.asset_map
	def get_event(self, event_id):
		duration = self.duration_map[event_id] if event_id in self.duration_map else None
		print(duration)
		return dict(asset_name=self.asset_map[event_id].title, 
					duration=duration)

	@classmethod
	def from_files(cls, mapping_file, asset_info):
		mapping_xml = ET.parse(mapping_file)
		event_mappings = dict(map(lambda match: (match.event_id, match), 
			map(lambda m: PrerecordedVideo.mapping_from_xml(m), mapping_xml.getroot())))
		duration_mappings = dict()
		with open(asset_info) as csvfile:
			reader = csv.DictReader(csvfile)
			fmt = "%H:%M:%S.%f"
			for row in reader:
				dt = datetime.datetime.strptime(row["Duration"], fmt)
				duration_mappings[row["Name"]] = \
					datetime.timedelta(hours=dt.hour, minutes=dt.minute, 
									   seconds=dt.second, microseconds=dt.microsecond)
		# we now have duration mappings! They're wrong though.
		# the map is of the form (lowercase) video_id[-video] => duration
		# we want something of the form event_id => duration
		# to do this, we need to combine event_mappings and duration_mappings
		event_duration_mapping = dict()
		for event_id, asset_id in event_mappings.items():
			if asset_id.title == None:
				continue
			asset_name = f"{asset_id.title.lower()}-video"
			if asset_name in duration_mappings:
				event_duration_mapping[event_id] = duration_mappings[asset_name]
		return VideoMapping(event_mappings, event_duration_mapping)

class EventRoom:
	def __init__(self, name, live_stream, filler_stream):
		self.name = name
		self.live = live_stream
		self.filler = filler_stream

	@classmethod
	def from_xml(cls, elem):
		return cls(elem.xpath("./@name")[0], elem.xpath("./@live")[0], elem.xpath("./@filler")[0])

class ZoomInfo:
	def __init__(self, room, url, stream):
		self.room = room
		self.url = url
		self.stream = stream
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
		if spec.has_zoom():
			out['zoom'] = spec.get_zoom(room)
		return out

	def schedule(self, mapping, rooms, spec, format, timeslot, now):
		out = dict()
		if self.plenary:
			for room in rooms:
				out_evt, new_now = self.schedule_one(mapping, room, spec, format, timeslot, now)
				out[room.name] = [out_evt]
		else: 
			for room in rooms:
				previous_now = None
				if room.name == timeslot.room:
					out_evt, new_now = self.schedule_one(mapping, room, spec, format, timeslot, now)
					out[room.name] = [out_evt]
					if new_now != previous_now and previous_now != None:
						raise RuntimeError("Repeated scheduling of a plenary event produced a different now time")
					elif previous_now == None:
						previous_now = new_now
		return out, new_now

class PrerecordedElement(ScheduleElement):
	def __init__(self, source, plenary=False):
		self.source = source
		self.plenary = plenary

	def schedule_one(self, mapping, room, spec, format, timeslot, now):
		ctx_dict = self.make_context_dict(room, spec, format, timeslot)
		
		if not mapping.has_event(timeslot.event_id):
			raise RuntimeError(f"Playing a prerecorded video for an unmapped event ({timeslot.event_id})!")
		asset_data = mapping.get_event(timeslot.event_id)

		if self.source != None:
			title = self.source.format(**ctx_dict)
		else:
			title = asset_data["asset_name"] # TODO
		category = "PROGRAM"

		if asset_data["duration"] != None:
			duration = asset_data["duration"]
		else:
			duration = datetime.timedelta() # representing 0 time
		endmode = "FOLLOW"
		onairtime = now
		m = None 
		ts = timeslot

		return PlaylistEvent(title, category, duration, endmode, onairtime, m, ts), now+duration

	@classmethod
	def from_xml(cls, elem):
		asset = None
		source = elem.xpath('./@source')
		if len(source) > 0:
			asset = source[0]

		plenary = elem.xpath('./@plenary')
		is_plenary = len(plenary) > 0 and plenary[0] == "true"
		return cls(asset, plenary=is_plenary)

class LiveElement(ScheduleElement): 
	def __init__(self, source, plenary=False, recording=None, xml_elem=None):
		self.source = source
		self.plenary = plenary
		self.recording = recording
		self.xml_elem = xml_elem

	def schedule_one(self, mapping, rooms, spec, format, timeslot, now):
		ctx_dict = self.make_context_dict(rooms, spec, format, timeslot)
		try: 
			title = self.source.format(**ctx_dict)
		except ValueError:
			print(f"invalid format string {self.source} in element on line {self.xml_elem.sourceline}")
			raise 
		category = "LIVE"
		duration = timeslot.end_ts - now
		endmode = "FOLLOW"
		onairtime = now # TODO
		m = None
		ts = timeslot
		return PlaylistEvent(title, category, duration, endmode, onairtime, m, ts), now+duration

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
	def __init__(self, cond, schedule):
		self.cond = cond
		self.schedules = schedule

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
			return scheduler.is_mirror(ts) == mirrored
		# mirror condition
		cond = prop_cond("./@mirror", lambda cond, mirrored: lambda sch, ts: is_mirror(sch, ts, mirrored=="true") and cond(sch, ts), cond)


    	# TODO: support badges

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

		return EventFormat(cond, schedule_elems)


class EventSpec:
	def __init__(self, name, formats):
		self.name = name
		self.formats = formats

	def schedule(self, scheduler, mapping, rooms, timeslot):
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
		return out


class Scheduler:
	def __init__(self, rooms, events, is_mirror = lambda ts: False):
		self.rooms = rooms 
		self.events = events
		self.events_map = dict()
		for event_spec in self.events:
			if not event_spec.name in self.events_map:
				self.events_map[event_spec.name] = event_spec
			else:
				raise RuntimeError(f"Repeated definition of event ${event_spec.name}!")

		self.is_mirror = is_mirror

	def schedule(self, mapping, timeslot):
		scheduler = None 
		for track in timeslot.tracks:
			if track in self.events_map:
				scheduler = self.events_map[track]
				break
		if scheduler == None:
			raise RuntimeError(f"Was unable to find a scheduler for event {timeslot.event_id} in tracks {timeslot.tracks}!")
		return scheduler.schedule(self, mapping, self.rooms, timeslot)

	@classmethod
	def from_xml(cls, elem):
		mirroring_els = elem.xpath("./mirroring")
		is_mirror = lambda ts: False
		if len(mirroring_els) > 0:
			mirroring_el = mirroring_els[0]
			# find when the main track starts and ends
			main_start = datetime.time.fromisoformat(mirroring_el.xpath("./@start")[0])
			main_end = datetime.time.fromisoformat(mirroring_el.xpath("./@end")[0])
			is_mirror = lambda ts: ts.start_ts.time() < main_start or ts.end_ts.time() > main_end
		rooms = list(map(EventRoom.from_xml, elem.xpath(".//rooms/room")))
		events = list(map(EventSpec.from_xml, elem.xpath(".//events/event")))
		return cls(rooms, events, is_mirror)

        

    
def gen_playlist(room_id, event_mappings, timeslots_mappings):
    """
    Given an map of event mappings and a map of event schedules generates a playlist 
    """
    event_ids = event_mappings.keys() & timeslots_mappings.keys()
    
    es = map(lambda x: gen_playlist_event(event_mappings[x], timeslots_mappings[x]), event_ids)

    pl = sorted(es, key=lambda x: x.onairtime)

    fillers = gen_fillers(room_id, pl)

    return list(sorted ((pl + fillers), key=lambda x: x.onairtime))
        
    
    
# prduces 3 files "SPLASH-2021-playlist-demo-Zurich{A|B|C}.xml"
if __name__ == '__main__':
    print("howdy")
    
    base_output_file = "SPLASH21-playlist-demo-Zurich-" # FIXME remove demo for final
    base_room = "Swissotel Chicago | Zurich "
    roomA = base_room + "A"
    room_ids = ["A", "B", "C"]
    
    rooms = [base_room + r for r in room_ids]

    mapping_xml = ET.parse("mapping.xml")

    # dictonary for event_id to confpub id mapping
    event_mappings = dict(map(lambda match: (match.event_id, match)
                              , map(lambda m: PrerecordedVideo.mapping_from_xml(m), mapping_xml.getroot())))

    schedule_xml = ET.parse("schedule.xml")

    schedule_timezone = TZ.gettz(schedule_xml.xpath("//timezone_id/text()")[0])

    print(f"for timezone {schedule_timezone}")

    # get all the time slots from all the subevents under events
    timeslots_xml = schedule_xml.getroot().xpath("//timeslot[event_id]")

    # we filter on only those timeslots that have an event_id and a badges node
    timeslots = []
    for ts in timeslots_xml:
        timeslots.append(TimeSlotSchedule.from_xml(schedule_timezone, ts))

    mapping = VideoMapping.from_files("mapping.xml", "asset-info.csv")
    parser = ET.XMLParser(remove_comments=True)
    scheduler = Scheduler.from_xml(ET.parse("liveinfo.xml", parser = parser))

    schedule = dict((room, []) for room in rooms)
    for ts in timeslots:
    	if not ts.room in rooms:
    		continue
    	for k,v in scheduler.schedule(mapping, ts).items():
    		schedule[k].extend(v)
    for k,v in schedule.items():
    	print(k)
    	v.sort(key=lambda evt: evt.onairtime)
    	for it in v:
    		print(it)

    # TODO: actually assemble the schedule
    # TODO: insert filler elements

    # mapping between even_ids and schedule timeslots
    timeslots_mappings = dict(map(lambda x: (x.event_id, x), timeslots))
    
    print(f"Parsed Schedule({len(timeslots)}) and event mappings({len(event_mappings)})")

    x = len (event_mappings.keys() - timeslots_mappings.keys())    
    if x:
        print(f"Warning: There are {x} events in event mappings that are not scheduled")

    x = len (timeslots_mappings.keys() - event_mappings.keys()) 
    if x:
        print(f"Warning: There are {x} events in the schedule but not in event mappings")
            
    for r in room_ids:
        current_room = base_room + r
        print(f"Generating Playlist for {current_room}")
        # filter timeslots for current room
        timeslots_mapping_for_room = dict(filter(lambda x: x[1].room == current_room, timeslots_mappings.items()))

        # a single event_id can appear more than once 
        # (they're duplicated for mirrored events)
        # so we can't build a map based on them. Only slot_ids are unique.
        
        # generate playlist for a room    
        root = ET.Element("playlist")
        eventlist = ET.Element("eventlist")
        eventlist.set("timeinmilliseconds", "false")
        root.append(eventlist)
        playlist_xml = map (PlaylistEvent.to_xml, generate_playlist(event_mappings, filter(lambda ts: ts.room == base_room + r, timeslots)))
        root.extend(list(playlist_xml))

        # write it to a file
        output_file = base_output_file + r + ".xml"
        print(f"writing to file {output_file}")
        with open(output_file, "wb") as xf:
            xf.write(ET.tostring(root, pretty_print=True, xml_declaration=True, encoding='utf-8', standalone=True))
        
    # TODO: find filler events in the timeline
    # TODO: Some manual events whose durations we don't know, cut through filler or zoom room (ANI: I don't undrstand this)
    # TODO: maybe take file names are arguments to the script.
    
    print("bye")
