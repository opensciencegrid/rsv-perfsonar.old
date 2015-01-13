import os
import time
from time import strftime
from time import localtime

from optparse import OptionParser
from fractions import Fraction

from esmond.api.client.perfsonar.query import ApiFilters
from esmond.api.client.perfsonar.query import ApiConnect
# New module with the socks5 that inherics ApiConnect
from SocksApiConnect import SocksApiConnect

from esmond.api.client.perfsonar.post import MetadataPost, EventTypePost, EventTypeBulkPost

#allowedEvents = ['packet-loss-rate', 'packet-trace', 'packet-retransmits', 'throughput', 'throughput-subintervals', 'failures', 'packet-count-sent', 'packet-count-lost', 'histogram-owdelay', 'histogram-ttl']

allowedEvents = ['packet-loss-rate', 'throughput', 'packet-trace', 'packet-retransmits', 'histogram-owdelay']

skipEvents = ['histogram-owdelay', 'histogram-ttl']


# Set filter object
filters = ApiFilters()
gfilters = ApiFilters()

# Set command line options
parser = OptionParser()
parser.add_option('-d', '--disp', help='display metadata from specified url', dest='disp', default=False, action='store')
parser.add_option('-e', '--end', help='set end time for gathering data (default is now)', dest='end', default=0)
parser.add_option('-l', '--loop', help='include this option for looping process', dest='loop', default=False, action='store_true')
parser.add_option('-p', '--post',  help='begin get/post from specified url', dest='post', default=False, action='store_true')
parser.add_option('-r', '--error', help='run get/post without error handling (for debugging)', dest='err', default=False, action='store_true')
parser.add_option('-s', '--start', help='set start time for gathering data (default is -12 hours)', dest='start', default=-43200)
parser.add_option('-u', '--url', help='set url to gather data from (default is http://hcc-pki-ps02.unl.edu)', dest='url', default='http://hcc-pki-ps02.unl.edu')
parser.add_option('-w', '--user', help='the username to upload the information to the GOC', dest='username', default='afitz', action='store')
parser.add_option('-k', '--key', help='the key to upload the information to the goc', dest='key', default='fc077a6a133b22618172bbb50a1d3104a23b2050', action='store')
parser.add_option('-g', '--goc', help='the goc address to upload the information to', dest='goc', default='http://osgnetds.grid.iu.edu', action='store')
parser.add_option('-t', '--timeout', help='the maxtimeout that the probe is allowed to run in secs', dest='timeout', default=1000, action='store')
parser.add_option('-x', '--summaries', help='upload and read data summaries', dest='summary', default=True, action='store')

(opts, args) = parser.parse_args()

class EsmondUploader(object):

    def add2log(self, log):
        print strftime("%a, %d %b %Y %H:%M:%S ", localtime()), log
    
    def __init__(self,verbose,start,end,connect,username='afitz',key='fc077a6a133b22618172bbb50a1d3104a23b2050', goc='http://osgnetds.grid.iu.edu'):

        # Filter variables
        filters.verbose = verbose
        filters.time_start = time.time() + start
        filters.time_end = time.time() + end
        # gfiltesrs and in general g* means connecting to the cassandra db at the central place ie goc
        gfilters.verbose = False        
        gfilters.time_start = time.time() + 5*start
        gfilters.time_end = time.time()
        gfilters.source = connect

        # Username/Key/Location/Delay
        self.connect = connect
        self.username = username
        self.key = key
        self.goc = goc
        self.conn = SocksApiConnect(self.connect, filters)
        self.gconn = ApiConnect(self.goc, gfilters)
                
        # Metadata variables
        self.destination = []
        self.input_destination = []
        self.input_source = []
        self.measurement_agent = []
        self.source = []
        self.subject_type = []
        self.time_duration = []
        self.tool_name = []
        self.event_types = []
        self.summaries = []
        self.datapoint = []
        self.metadata_key = []
        self.old_list = []
   
    # Get Existing GOC Data
    def getGoc(self, disp=False):
        if disp:
            self.add2log("Getting old data...")
        for gmd in self.gconn.get_metadata():
            self.old_list.append(gmd.metadata_key)
   
    # Get Data
    def getData(self, disp=False, summary=True):
        self.getGoc(disp)
        self.add2log("Only reading data for event types: %s" % (str(allowedEvents)))
        #self.add2log("Skipped reading data for event types: %s" % (str(skipEvents)))
        if summary:
            self.add2log("Reading Summaries")
        else:
            self.add2log("Omiting Sumaries")
        for md in self.conn.get_metadata():
            # Check for repeat data
            if md.metadata_key in self.old_list:
                continue
            else:
                # It is a new metadata
                # Building the arguments for the post
                args = {
                    "subject_type": md.subject_type,
                    "source": md.source,
                    "destination": md.destination,
                    "tool_name": md.tool_name,
                    "measurement_agent": md.measurement_agent,
                    "input_source": self.connect,
                    "input_destination": self.goc
                }
                if not md.time_duration is None:
                    args["time_duration"] = md.time_duration
                # Assigning each metadata object property to class variables
                event_types = md.event_types
                metadata_key = md.metadata_key
                # print extra debugging only if requested
                self.add2log("Reading New METADATA/DATA %s" % (md.metadata_key))
                if disp:
                    print args
                # Get Events and Data Payload
                # temp_list holds the sumaries for all event types for metadata i
                summaries = [] 
                # datapoints is a dict of lists
                # Each of its members are lists of datapoints of a given event_type
                datapoints = {}
                # et = event type
                for eventype in event_types: 
                    datapoints[eventype] = []
                    et = md.get_event_type(eventype)
                    if summary:
                        summaries.append(et.summaries)
                    else:
                        summaries.append([])
                    # Skip readind data points for certain event types to improv efficiency  
                    if eventype not in allowedEvents:                                                                                                       
                    #if eventype in skipEvents:
                        #self.add2log("Skipped reading data for event type: %s for metadatda %d" % (eventype, i+1))
                        continue
                    dpay = et.get_data()
                    for dp in dpay.data:
                        tup = (dp.ts_epoch, dp.val)
                        datapoints[eventype].append(tup)
            self.postData2(args, event_types, summaries, metadata_key, datapoints, disp)


    def postData2(self, args, event_types, summaries, metadata_key, datapoints, disp=False):
        mp = MetadataPost(self.goc, username=self.username, api_key=self.key, **args)
        for event_type, summary in zip(self.event_types, self.summaries):
            mp.add_event_type(event_type)
            if summary:
                mp.add_summary_type(event_type, summary[0][0], summary[0][1])
        self.add2log("posting NEW METADATA/DATA")
        new_meta = mp.post_metadata()
        # Catching bad posts                                                                                                                              
        try:
            new_meta.metadata_key
        except:
            print 'ERROR'
            print args
            print event_types
            print summaries
            return
        self.add2log("Finished posting summaries and metadata")
        et = EventTypeBulkPost(self.goc, username=self.username, api_key=self.key, metadata_key=new_meta.metadata_key)
        for event_type in event_types:
            # datapoints are tuples the first field is epoc the second the value                                                                          
            for datapoint in datapoints[event_type]:
                # packet-loss-rate is read as a float but should be uploaded as a dict with denominator and numerator                                     
                if 'packet-loss-rate' in event_type:
                    if isinstance(datapoint[1], float):
                        packetLossFraction = Fraction(datapoint[1]).limit_denominator(300)
                        et.add_data_point(event_type, datapoint[0], {'denominator':  packetLossFraction.denominator, \
                                                                             'numerator': packetLossFraction.numerator})
                    else:
                        self.add2log("weird packet loss rate")
                    # For the rests the data points are uploaded as they are read                                                                            
                else:
                    et.add_data_point(event_type, datapoint[0], datapoint[1])
        # Posting the data once all data points on the same metadata have been added                                                                     
        et.post_data()
        self.add2log("Finish posting data for metadata")

