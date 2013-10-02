from xml.etree.ElementTree import ElementTree, Element, SubElement
import xml.etree.ElementTree as etree
import bpy
import os

print("----------------------------------------------------------")


### VARIABLES
fileName = bpy.path.basename(bpy.data.filepath)
fileBasename = fileName.split(".")[0]

context = bpy.context

system = context.user_preferences.system
audioRate = int(system.audio_sample_rate.split("_")[1])
    
scene = context.scene
startFrame = scene.frame_start
endFrame = scene.frame_end

desktop = os.environ['HOMEPATH'] + os.sep + "Desktop"
sourceAudiosFolder = desktop # change, must come from User choice



######## ---------------------------------------------------------------------------
######## Timeline and Settings
######## ---------------------------------------------------------------------------

def checkSampleFormat():
    sampleFormat = system.audio_sample_format
    if (sampleFormat == "S16"):
        sampleFormat = "FormatInt16"        
    elif (sampleFormat == "S24"):
        sampleFormat = "FormatInt24"
    elif (sampleFormat == "FLOAT"):
        sampleFormat = "FormatFloat"
    else:
        raise TypeError('Sample Format ' + sampleFormat + ' not supported by Ardour.\
                         Change Sample Format in Blender\'s User Settings.')
    return sampleFormat
    
def checkFPS():
    if (scene.render.fps in [23.976, 24, 24.975, 25, 29.97, 30, 59.94, 60]): # Ardour valid FPSs
        fps = scene.render.fps
    else:
        fps = 24
    return fps

def toSamples(fr, ar=audioRate, fps=24):
    return int(fr * audioRate / fps)

def getAudioTimeline():
    timelineSources = []
    timelineRepeated = []
    for i in bpy.context.sequences:
        #if (i.select):
        if (i.type == "SOUND"):
            start = toSamples(i.frame_offset_start)
            position = toSamples(i.frame_start + i.frame_offset_start - 1)
            length = toSamples(i.frame_final_end - (i.frame_start + i.frame_offset_start))
        
            audioData = {'name': i.name,
                         'base_name': i.name.split(".")[0],
                         'ext': i.name.split(".")[1],
                         'id': "",
                         'length': length,
                         'origin': i.filepath,                  
                         'position': position,
                         'start': start,
                         'track': "Channel %i" % i.channel
                         }
                  
            if (i.mute):
                audioData['muted'] = 1
            else:
                audioData['muted'] = 0
        
            if (i.lock):
                audioData['locked'] = 1
            else:
                audioData['locked'] = 0
                
            if audioData['ext'].upper() in ["AAC", "AC3", "FLAC", "MP2", "MP3", "OGG", "WAV"]:
                audioData['nExt'] = 1
                audioData['ardour_name'] = "%s.%i" % (audioData['base_name'], audioData['nExt'])
                timelineSources.append(audioData)
            else:
                audioData['nExt'] = int(i.name.split(".")[1]) + 1
                audioData['ardour_name'] = "%s.%i" % (audioData['base_name'], audioData['nExt'])
                timelineRepeated.append(audioData)

    return timelineSources, timelineRepeated


######## ---------------------------------------------------------------------------
######## XML
######## ---------------------------------------------------------------------------

def createSubElements(el, att):
    for key, value in att.items():
        el.set(key, str(value))

def createSubElementsMulti(el, att, count):
    for key, value in att.items():
        el.set(key, str(value[count]))

def valLength(dic):
    '''Returns length of dictionary values'''
    return len(next(iter(dic.values())))

######## ---------------------------------------------------------------------------
######## SKELETAL XML
######## ---------------------------------------------------------------------------

def atSession():
    atSession = {'version': 3001,
                 'name': fileBasename,
                 'sample-rate': audioRate,
                 'id-counter': idCounter,
                 'event-counter': 0
                 }
    return atSession

def atOption():
    timecode = "timecode_%s" % fps # check validity in ardour for many FPSs
    format = checkSampleFormat()
    atOption = {'name': ["audio-search-path", "timecode-format",
                         "use-video-file-fps", "videotimeline-pullup", 
                         "native-file-data-format"],
                'value': [sourceAudiosFolder, timecode, 
                          1, 0, 
                          format] # blender project fps
                          # 1 in use-video-file-fps = use video file's fps instead of timecode value for timeline and video monitor
                          # 0 in videotimeline-pullup = apply pull-updown to video timeline and video monitor (unless in jack-sync)
                }
    return atOption

def atLocation():
    atLocation = {'id': idCounter,
                  'name': "session",
                  'start': ardourStart,
                  'end': ardourEnd,
                  'flags': "IsSessionRange",
                  'locked': "no",
                  'position-lock-style': "AudioTime"
                  }
    return atLocation

def atIO():
    atIO = {'name': "click",
            'id': idCounter,
            'direction': "Output",
            'default-type': "audio",
            'user-latency': 0,
            }
    return atIO

def atPort():
    atPort = {'type': ["audio", "audio"],
              'name': ["click/audio_out 1", "click/audio_out 2"]
              }
    return atPort

def atTempo():
    atTempo = {'start': "1|1|0",
               'beats-per-minute': "120.000000",
               'note-type': "4.000000",
               'movable': "no"
               }
    return atTempo
           
def atMeter():
    atMeter = {'start': "1|1|0",
               'note-type': "4.000000",
               'divisions-per-bar': "4.000000",
               'movable': "no"
               }
    return atMeter

######## ---------------------------------------------------------------------------
######## SKELETAL AUDIO TRACK
######## ---------------------------------------------------------------------------

#def atSource(name, idCounter):
def atSource(strip):
    atSource = {'channel': 0, # ???????
                'flags': "",
                'id': strip['id'], # change id accordingly - this id influentiates atRegion in source-o and master-source-0
                'name': strip['name'], # audio file with extension
                'origin': strip['name'], # audio file with extension - could be an absolute path                
                'type': "audio"
                }
    return atSource

def atRegion(strip, idCount):
    atRegion = {'channels': 1, # mono file --- CHECK FROM BLENDER TIMELINE
                'id': idCount, # generic id
                'length': strip['length'],
                'locked': strip['locked'],
                'master-source-0': strip['sourceID'], # this is same id as atSource's id -------!!!!!!!
                'muted': strip['muted'],
                'name': strip['ardour_name'],
                'position': strip['position'],
                'source-0': strip['sourceID'], # this is same id as atSource's id -------!!!!!!!
                'start': strip['start'],
                
                'ancestral-length': 0,
                'ancestral-start': 0,
                'automatic': 0,                
                'default-fade-in': 0,
                'default-fade-out': 0,
                'envelope-active': 0, # envelope in Ardour is same as metastrip in Blender?
                'external': 1, # 1 = not imported to ardour's assets folder?
                'fade-in-active': 1,
                'fade-out-active': 1,
                'first-edit': "nothing",
                'hidden': 0, # 0 = not hidden                
                'import': 0,
                'layering-index': 0,
                'left-of-split': 0,                
                'opaque': 1,                
                'position-locked': 0, # 0 = not locked
                'positional-lock-style': "AudioTime",                
                'right-of-split': 0,
                'scale-amplitude': 1,
                'shift': 1,                
                'stretch': 1,
                'sync-marked': 0,
                'sync-position': 0,
                'type': "audio",
                'valid-transients': 0,
                'video-locked': 0, # 0 = not locked? should be locked to video?
                'whole-file': 0 # 1 = whole file? I'm using whole file for this test
                }
    return atRegion

######## ---------------------------------------------------------------------------
######## CREATE AUDIO TRACK
######## ---------------------------------------------------------------------------

def createAudioSources(strip, idCount):
    Source = SubElement(Session[2], "Source")
    #Region = SubElement(Session[3], "Region")

    createSubElements(Source, atSource(strip))
    idCount += 1
    
    #createSubElements(Region, atRegion(strip, idCount))
    #idCount += 1
    
    idCounter = idCount
    global idCounter

def createSourcesRegions(strip, idCount):
    Region = SubElement(Session[3], "Region")
    
    createSubElements(Region, atRegion(strip, idCount))
    idCount += 1

    idCounter = idCount
    global idCounter
        
######## ---------------------------------------------------------------------------
######## CREATE SKELETAL XML
######## ---------------------------------------------------------------------------

audios, repeated = getAudioTimeline()
fps = checkFPS()
sampleFormat = checkSampleFormat()
ardourStart = toSamples((startFrame-1), audioRate, fps)
ardourEnd = toSamples((endFrame-1), audioRate, fps)


######## ---------------------------------------------------------------------------
# XML root = Session
Session = Element("Session")
tree = ElementTree(Session)

# Create Session Elements + Attributes
idCounter = 0
xmlSections = [ "Config", "Metadata", "Sources", "Regions", "Locations", "Bundles",
             "Routes", "Playlists", "UnusedPlaylists", "RouteGroups", "Click",
             "Speakers", "TempoMap", "ControlProtocols", "Extra" ]

for section in xmlSections:
    Session.append(Element(section))

# Create Option, IO, Tempo and Meter + Attributes
for counter in range(valLength(atOption())): #
    Option = SubElement(Session[0], "Option") # Session > Config > Option
    createSubElementsMulti(Option, atOption(), counter)

Location = SubElement(Session[4], "Location") # Session > Locations > Location
IO = SubElement(Session[10], "IO") # Session > Click > IO
Tempo = SubElement(Session[12], "Tempo") # Session > TempoMap > Tempo
Meter = SubElement(Session[12], "Meter")# Session > TempoMap > Meter

createSubElements(Session, atSession())    
createSubElements(Location, atLocation()); idCounter += 1 # idCounter = 1
createSubElements(IO, atIO()); idCounter += 1 # idCounter = 2
createSubElements(Tempo, atTempo())
createSubElements(Meter, atMeter())

Port = ""
for counter in range(valLength(atPort())):
    Port = SubElement(IO, "Port") # Session > Click > IO > Port
    createSubElementsMulti(Port, atPort(), counter)

# idCounter = 2

######## ---------------------------------------------------------------------------

# create sources and sources regions
for strip in audios:
    strip['id'] = idCounter
    strip['sourceID'] = idCounter
    createAudioSources(strip, idCounter)
    createSourcesRegions(strip, idCounter)

# correct reference to sources in other regions
for aud, rep in zip(audios, repeated):
    if (rep['origin'] == aud['origin']):
        rep['sourceID'] = aud['id']
        print(aud['name'], aud['id'], rep['name'], rep['sourceID'])
        
for strip in repeated:        
    strip['id'] = idCounter
    createSourcesRegions(strip, idCounter)    
    #print(strip['name'], strip['nExt'], strip['ardour_name'])

#### SOURCES MUST NOT CREATE ENTRIES FOR .001 FILES
#### REGIONS FOR .001 FILES MUST REFERENCE ORIGINAL .WAV FILES



#print(ardourStart, ardourEnd)
#print(audios[0])


















######## ---------------------------------------------------------------------------
######## WRITE TO FILE
######## ---------------------------------------------------------------------------

Session.set('id-counter', str(idCounter))


from xml.dom.minidom import parseString

def identXML(element):
    return parseString(etree.tostring(element, "UTF-8")).toprettyxml(indent="  ")

outXML = desktop + os.sep + fileBasename + ".xml" # should be similar to #sourceAudiosFolder, get from UI
with open(outXML, 'w') as xmlFile:
    xmlFile.write(identXML(Session))

#os.environ['HOMEPATH'] + os.sep + "Desktop"
