# ##### BEGIN GPL LICENSE BLOCK #####
#
#  Copyright (c) 2026 CarnageZore
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 3
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, see <https://www.gnu.org/licenses/>.
#
# ##### END GPL LICENSE BLOCK #####

import sys, os, mathutils, math, random, shutil
import bpy, bmesh
import xml.etree.ElementTree as XmlTree
from bpy.props import *
from mathutils import Vector
import addon_utils as au
import importlib
from enum import Enum

addon_path = os.path.dirname(__file__)

from munchs_oddysee_tag_manager.LoadNif import NetImmerseFileParser
from munchs_oddysee_tag_manager.LoadNif import LoadAllModelsFromGame
from munchs_oddysee_tag_manager.LoadNif import LoadAndExportModel
from munchs_oddysee_tag_manager.LoadNif import mylist

printstack = []

class InfoPusher(bpy.types.Operator):
    bl_idname = "wm.info_push"
    bl_label = "Push message to info page"
    
    def execute(self, context):
        for m in printstack:
            self.report({'INFO'}, str(m))
        return {'FINISHED'}

bpy.utils.register_class(InfoPusher)

def AbsPath(path):
    return os.path.abspath(bpy.path.abspath(path)).replace("\\", "/")

def CreateFolder(path):
    if os.path.exists(path): return
    os.makedirs(path)

def Hardlink(sourcefile, filepath):
    if os.path.exists(filepath): return
    os.link(sourcefile, filepath)

# pretty sure this didnt work??
def INFO(*messages):
    global printstack
    printstack = [m for m in messages]
    bpy.ops.wm.info_push()

# Shader Stuff
def quicklink(node_tree, OutNode, index_out, InNode, index_in):
     node_tree.links.new(node_tree.nodes[OutNode].outputs[index_out], node_tree.nodes[InNode].inputs[index_in])
     
def HudLightMaterial(material):
    node_tree = material.node_tree
    nodes = node_tree.nodes
    links = node_tree.links
    
    if not nodes.get("Mix Shader") == None: return
    
    material.surface_render_method = "BLENDED"
    
    nodes.new("ShaderNodeBsdfPrincipled")
    nodes["Principled BSDF.001"].location = nodes["Principled BSDF"].location
    nodes["Principled BSDF.001"].location[1] += 320
    
    nodes.new("ShaderNodeMath")
    nodes["Math"].location = nodes["Principled BSDF.001"].location
    nodes["Math"].location[1] += 150
    
    nodes.new("ShaderNodeAttribute")
    nodes["Attribute"].location = nodes["Principled BSDF.001"].location
    nodes["Attribute"].location[0] -= 160
    nodes["Attribute"].location[1] += 80
    nodes["Attribute"].attribute_type = "OBJECT"
    nodes["Attribute"].attribute_name = "lamp_on"
    
    nodes["Material Output"].location[0] += 200
    
    nodes.new("ShaderNodeMixShader")
    nodes["Mix Shader"].location = nodes["Material Output"].location
    nodes["Mix Shader"].location[0] -= 160
    nodes["Mix Shader"].location[1] -= 22
    
    nodes["Image Texture"].location[0] -= 100
    
    nodes.new("ShaderNodeValToRGB")
    nodes["Color Ramp"].location = nodes["Image Texture"].location
    nodes["Color Ramp"].location[1] -= 270
    
    
    if not nodes.get("Image Texture.001") == None:
        nodes.remove(nodes["Image Texture.001"])
    
    nodes["Math"].operation = "GREATER_THAN"
    nodes["Math"].inputs[0].default_value = 0
    nodes["Math"].inputs[1].default_value = 0
    nodes["Math"].use_clamp = True
    
    
    nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 1    
    nodes["Principled BSDF.001"].inputs[4].default_value = 0
            
    quicklink(node_tree, "Mix Shader", 0, "Material Output", 0)
    quicklink(node_tree, "Attribute", 2, "Math", 0)
    quicklink(node_tree, "Math", 0, "Mix Shader", 0)
    
    quicklink(node_tree, "Principled BSDF.001", 0, "Mix Shader", 1)
    quicklink(node_tree, "Principled BSDF", 0, "Mix Shader", 2)
    
    quicklink(node_tree, "Image Texture", 0, "Principled BSDF", 0)
    quicklink(node_tree, "Image Texture", 0, "Principled BSDF", "Emission Color")
    
    quicklink(node_tree, "Image Texture", 0, "Color Ramp", 0)
    quicklink(node_tree, "Color Ramp", 0, "Principled BSDF", "Alpha")

def shade_smooth(obj):
    for poly in obj.data.polygons:
        poly.use_smooth = True

def apply_scale(obj):
    mesh = obj.data
    val = obj.scale[0]
    sm = mathutils.Matrix.Diagonal((val,val,val,val))
    mesh.transform(sm)
    obj.scale = (1,1,1)

def LAYOUT_PROP_LST(layout, pg, propnamelist:list, showHasAttrs):
    layout.prop(pg, "search")
    search_res = pg.search.lower().strip()
    if showHasAttrs:
        box = layout.box()
        for prop in propnamelist:
            if search_res == "" or search_res in prop:
                box.prop(pg, f"has_{prop}")
    for prop in propnamelist:
        if not getattr(pg, f"has_{prop}"): continue
        if search_res == "" or search_res in prop:
            layout.prop(pg, prop)

def GENERATE_PROP_LST(tag, pg, proplist:list):
    for name in proplist:
        has = getattr(pg,f"has_{name}")
        val = getattr(pg,name)
        if pg.bl_rna.properties[name].type == "POINTER":
            print(f"POINTER VALUE: {pg[name]}")
            # Weird stuff with the pointer here...
            # if i access it like this type(pg.attrname) then it gives NoneType
            # but if i access it like this type(pg["attrname"]) then it gives IDPropertyGroup
            # so I have to handle that seperately (Ill just check if it is not the wrong type or None)
            if type(pg[name]) is not bpy.types.Object or pg[name]== None:
                tag += f"{name}='' "
            else:
                tag += f"{name}='{pg[name].XinGUID.value}' "
        else:
            default = pg.bl_rna.properties[name].default
            if type(default) == bool: 
                val = BOOL(val)
                default = BOOL(default)
            if has and not val == default:
                if pg.bl_rna.properties[name].type == "FLOAT":
                    if pg.bl_rna.properties[name].is_array:
                        if pg.bl_rna.properties[name].subtype == "XYZ":
                            tag += f"{name}='{VECT(tuple(val))}' " # shenanigans
                        elif pg.bl_rna.properties[name].subtype == "COLOR":
                            tag += f"{name}='{COLOR(tuple(val))}' "
                    else:
                        tag += f"{name}='{round(val,3)}' "
                else:
                    tag += f"{name}='{val}' "
    return tag
    
## UK 10/09/2024 21:43 -- CarnageZore   
# The ONLY requirement for an actor to be recognised as one is for it to be inside the markers collection
# then you can start adding properties and components to the actor all though some combinations may cause the 
# game to crash. This allows for increased flexablility when designing actors.


## UK 22/12/2024 02:11 -- CarnageZore   
# NEXT TASK
# Go through all components has_attrs and set them to true if they
# should be there by default
# DONE

## UK 24/12/2024 21:59 -- CarnageZore
# To Do List
# * Make sure all attriutes in the actor class that should be Enums; are. 
# * Add the non actor classes and a way to add them to the scene
# * Change all GUID selectors to Object pickers so they can reference an object in the
#       scene as to not rely on the users memory of guids which may change.
# * Come up with a solution for object lists. (GUID lists).
# * Add all of the update functions for enums and checkboxes to change the models etc.
# * Create and set up all of the models that represent each marker 
#       in blender and all of their variants.



currenttag = ""

from bpy.types import (
    Panel,
    Operator,
    PropertyGroup,
    Menu
)

# use this when exporting water with value 32
def subdiv_to(segment_size):
    size = bpy.context.object.scale.x * 2
    bpy.ops.mesh.subdivide(number_cuts=int(size / segment_size - 1))

""" GUID """
class GUID(PropertyGroup):
    hasGUID: BoolProperty(
        name="GUID",
        description="The flag for if the guid was set on this object",
        default=False
    )
    value: IntProperty(
        name="GUID",
        description="The value of the guid",
        default=0
    )
    
def SelectObject(obj):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)

def CustomNifImport(filename):
    
    parser = NetImmerseFileParser()
    
    
    
    pass
    
def AddToDict(dic, keys, value):
    for key in keys:
        dic[key] = value
    return dic

def ConcatWithDilemiter(list, dilemiter):
    res = ""
    for item in list:
        res += res + ","
    return res[:-1]

def ConcatDrawsWithDilemiter(list, dilemiter):
    res = ""
    for item in list:
        res += item.draw() + ","
    return res[:-1]

def BOOL(value:bool):
        return 1 if value else 0

def VECT(value:tuple):
    res = ""
    for v in value:
        res += f"{round(v,3)},"
    return res[:-1]

def COLOR(value:tuple):
    res = ""
    for v in value:
        res += f"{round(v*255.0,3)},"
    return res[:-1]

"""
load_markers, collection:str, data:list:tuple(str,str)
colection - The name of the collection that these markers will be stored in
data - a list of tuples defining the markers to load
data entry:
    dataName - as displayed in the object data
    path - the relative path to the obj file to load
"""
def add_simple_marker(collection:str, name, primitive_func):
    print("entered add_simple_marker")

    ROOT_COLL = bpy.data.collections["Marker_Objects_DO_NOT_EDIT"]
    if ROOT_COLL.children.get(collection) == None:
        newcol = bpy.data.collections.new(collection)
        ROOT_COLL.children.link(newcol)

    COLL = ROOT_COLL.children[collection]
    
    OG_obj = bpy.context.object
    
    if not COLL.objects.get(name) == None: return
    
    obj = primitive_func()
    
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    
    COLL.objects.link(obj)
    bpy.context.collection.objects.unlink(obj)
    
    obj.hide_viewport = True
    
    SelectObject(OG_obj)

def import_obj(obj_path):
    #obj_path = "/mnt/data/SteamLibrary/steamapps/common/Oddworld Munchs Oddysee/editor/markers/mechanics/door/xcmet-00doo02_bv/xcmet-00doo02_bv.obj"

    # Import the OBJ file (without vertex groups)
    bpy.ops.wm.obj_import(filepath=obj_path, use_split_groups=False, forward_axis='Y', up_axis='Z')

    # Get the imported object
    imported_obj = bpy.context.selected_objects[-1]
    mesh = imported_obj.data

    # Dictionary to store vertex indices for each group
    group_verts = {}

    # Read the OBJ file to parse 'g' statements
    with open(obj_path, 'r') as f:
        vert_idx = 0
        current_group = "default"
        
        for line in f:
            if line.startswith('g '):
                current_group = line.strip().split(' ', 1)[1]
                if current_group not in group_verts:
                    group_verts[current_group] = []
            elif line.startswith('v '):
                vert_idx += 1
            elif line.startswith('f '):
                # Extract vertex indices from face definition
                face_verts = [int(part.split('/')[0]) - 1 for part in line.strip().split()[1:] if part]
                group_verts[current_group].extend(face_verts)

    # Create vertex groups and assign vertices
    for group_name, verts in group_verts.items():
        if verts:
            vg = imported_obj.vertex_groups.get(group_name)
            if not vg:
                vg = imported_obj.vertex_groups.new(name=group_name)
            vg.add(list(set(verts)), 1.0, 'ADD')

def load_markers(collection:str, data:list):
    
    print("entered load_markers")
    
    # Validate correct game path
    GR = bpy.context.scene.XinMO_Folder.gameroot
    if not os.path.exists(GR) or (
        not os.path.exists(f"{GR}/characters")) or (
        not os.path.exists(f"{GR}/mechanics")) or (
        not os.path.exists(f"{GR}/layout")) or (
        not os.path.exists(f"{GR}/vehicles")):
        print("ERROR: game path not valid! Please set the Game Root to a valid MO folder (must contain the: 'characters', 'mechanics', 'layout' and 'vehicles' folders)")
        return
        
    # Validate existence of marker data
    if not os.path.exists(f"{GR}/editor/markers"):
        print("ERROR: markers not generated! please press the 'Load All Assets' button")
        return
    
    print("Loading Markers: ", collection, data)
    
    ROOT_COLL = bpy.data.collections["Marker_Objects_DO_NOT_EDIT"]
    if ROOT_COLL.children.get(collection) == None:
        newcol = bpy.data.collections.new(collection)
        ROOT_COLL.children.link(newcol)

    COLL = ROOT_COLL.children[collection]
    
    OG_obj = bpy.context.object
    
    for name, path in data:
        path = f"{GR}/editor/{path}"
        if COLL.objects.get(name) != None: continue
        filename = path.split("/")[-1][:-4]
        
        import_obj(AbsPath(path))
        #bpy.ops.wm.obj_import(
        #    filepath=os.path.abspath(path), 
        #    forward_axis='Y', up_axis='Z',
        #    import_vertex_groups=True
        #)
        #obj = bpy.data.objects.get(filename)
        #print(obj)
        #print(bpy.context.object)
        obj = bpy.context.object
        obj.name = name
        obj.data.name = name
        
        if COLL.objects.get(obj.name) == None:
            COLL.objects.link(obj)
            bpy.context.collection.objects.unlink(obj)
        
        obj.hide_viewport = True
    
    SelectObject(OG_obj)
    
    pass

def smartenum(*List:tuple[str,int]|str):
    Result = {}
    LastValue = 0
    for Item in List:
        if type(Item) is tuple:
            LastValue = Item[1]
            Item = Item[0]
        Result[Item] = LastValue
        LastValue += 1
    return Result

''' ZORE RANT
    These map to the sockets of the GN modifiers
    as the sockets cannot be named in the GN editor and are 'Socket_{creation index}[_use_attribute,_attribute_name]' 
    and this is not codusive to programatic functionality so has to be hard coded like this.
    as such this abstracts away the hard codednes behind the Names rather than a random number wich was chosen by the node editor that cant be changed

    if the values were stored in a class like:
        class Socket:
            value = None
            use_attribute = False
            attribute_name = ""

    instead of:
    modifier = {
        "Socket_1" : 0, 
        "Socket_1_use_attribute" : False, 
        "Socket_1_attribute_name":"", 
        "Socket_2" : 0,
        "Socket_2_use_attrubute" : "False"
        ...
    }
    where the asockets are all grouped together in a mess.
    even if it were:
    modifier = {
        "Socket_1" : {
            "value" : 0,
            "use_attribute" : False,
            "attribute_name" : ""
        },
        ...
    }
    this would be better but is also doesnt use the input name and still only uses the generic Socket_{creation index}
    Idealy it would use a class or dict as the sockets internal structure and the name of the socket at the key
    dict
    modifier = {
        "Open" : {
            "value" : 0,
            "use_attribute" : False,
            "attribute_name" : ""
        },
        ...
    }
    class
    modifier = {
        "Open" : Socket(
            value=0, 
            use_attribute=False, 
            attribute_name=""
        ),
        ...
    } '''
node_group_socket_map = {
    "Ladder" : {
            "HeightVerts"   : 4,
            "Height"        : 5,
            "WidthL"        : 10,  
            "WidthR"        : 11,  
            "WidthCenter"   : 14,  
            "Width"         : 8,
            "Remaining"     : 9
        },
    "NatRegularDoor" : smartenum(
            ("Open"             , 13),
            ("Hinge Left"       , 7 ),
            "Hinge Right",
            "Door Near Left",
            "Door Near Right",
            "Door Far Left",
            "Door Far Right",
            ("Hinge Arm Left"   , 14),
            "Hinge Arm Right",
            "Frame" 
        ),
    "NatBigDoor" : {
            "Open"      : 13,
            "Door"      : 7,
            "Poles"     : 8,
            "Static"    : 9 
        },
    "CivRegularDoor" : smartenum(
            ("Open", 25),
            ("Lock", 2),
            "LockBladeL",
            "LockBladeR",
            "Core",
            "CoreLock",
            "Blade7L",
            "Blade1L",
            "Blade2L",
            "Blade3L",
            "Blade4L",
            "Blade5L",
            "Blade6L",
            "Blade7R",
            "Blade1R",
            "Blade2R",
            "Blade3R",
            "Blade4R",
            "Blade5R",
            "Blade6R",
            "Frame",
            "FrameInner",
            "Base",
            "CoreBase" 
        ),       
    "CivBigDoor" : {
            "Open"          : 13,
            "Door Upper"    : 7,
            "Door Lower"    : 9,
            "Poles"         : 8 
        },
    "VykkerDoor" : {
            "Open"  : 25,
            "DoorL" : 3,
            "DoorR" : 4,
            "Frame" : 22 
        },
    "SewerDoor" : smartenum(
            ("Open"     , 2),
            "Crossbar",
            "Bars1",
            "Bars3",
            "Bars2",
            "Frame" 
        ),
    "Well"  : smartenum(
            ("Open", 2),
            "Frame",
            "Glow",
            ("Blackhole", 6),
            "Segment 1",
            "Segment 2",
            "Segment 3",
            "Segment 4",
            "Segment 5"
        ),
    "WellBlowhole"  : smartenum(
            ("Open", 2),
            "Frame",
            "Glow",
            ("Blackhole", 6),
            "Segment 1",
            "Segment 2",
            "Segment 3",
            "Segment 4",
            "Segment 5"
        ),
    "BadShadowFix" : {"shadow" : 2},
    "Ground_Grid" : smartenum(
        ("Width", 8),
        "Height",
        "X",
        "Y",
        "Z"),
    "hcrane" : smartenum(
        ("width", 11),
        "height",
        "offsetX",
        "offsetY"),
    "ScriptTrigger" : {
        "width" : 2,
        "height" : 3 },
    "LayoutTransition" : {
        "width" : 2,
        "height" : 3 },
    "CameraTransition" : {
        "width" : 2,
        "height" : 3 },
}

def set_material(obj, slot:int, matname:str):
    obj.data.materials[slot] = bpy.data.materials[matname]
    obj.data.update()

def set_mesh(obj, meshname):
    og_obj = bpy.context.object
    obj.data = bpy.data.meshes[meshname]
    SelectObject(og_obj)

def add_modifier(obj, type, name):
    if obj.modifiers.get(name) == None:
        obj.modifiers.new(name=name, type=type)

def set_modifier_node_group(obj, modifier_name, node_group=""):
    if modifier_name == None: 
        obj.modifiers.clear()
        return
    if obj.modifiers.get(modifier_name) == None:
        obj.modifiers.new(name=modifier_name, type="NODES")
    if bpy.data.node_groups.get(node_group) == None: return
    obj.modifiers[modifier_name].node_group = bpy.data.node_groups[node_group]

def set_modifier_socket(obj, modifier_name:str, socket_name:str, value, use_attribute:bool = False):
    node_group = obj.modifiers[modifier_name].node_group.name
    prefix = f"Socket_{node_group_socket_map[node_group][socket_name]}"
    
    obj.modifiers[modifier_name][f"{prefix}_use_attribute"] = use_attribute
    if use_attribute: 
        obj.modifiers[modifier_name][f"{prefix}_attribute_name"] = value
    else:
        obj.modifiers[modifier_name][f"{prefix}"] = value
    obj.data.update()

def get_modifier_socket(obj, modifier_name, name):
    return f"Socket_{node_group_socket_map[obj.modifiers[modifier_name].node_group.name].get(name)}"

#METHODs

# 'make_path_absolute' modified to work with individual property groups and other functionality:
# SOURCE: https://sinestesia.co/blog/tutorials/avoid-relative-paths/
def make_path_absolute(pg, key): 
    """ Prevent Blender's relative paths of doom """ 
    sane_path = AbsPath(p) 
    if pg[key].startswith('//'): 
        path = sane_path(pg[key]).split("Oddworld Munchs Oddysee")[1].replace("\\","/")
        pg[key] = f'./..{path}'

def update_tagtype(sender, context):
    obj = context.object
    update_mesh(context)
    #obj.XinMeshController.update_mesh(context)
    
def poll_poll(obj, tagtype):
    if not obj.XinTagType == tagtype: return None
    if obj == bpy.context.object: return None
    coll = bpy.data.collections["MARKERS"].all_objects
    if coll.find(obj.name) == -1: return None
    return obj

def poll_actors(group, obj: bpy.types.Object):
    return poll_poll(obj, 'actor')
def poll_waypoints(group, obj: bpy.types.Object):
    return poll_poll(obj, 'waypoint')
def poll_cameras(group, obj: bpy.types.Object):
    return poll_poll(obj, 'camera')
def poll_cameratransitions(group, obj: bpy.types.Object):
    return poll_poll(obj, 'cameratransition')
def poll_scripttriggers(group, obj: bpy.types.Object):
    return poll_poll(obj, 'scripttrigger')
def poll_layouttransitions(group, obj: bpy.types.Object):
    return poll_poll(obj, 'layouttransition')
def poll_ambiances(group, obj: bpy.types.Object):
    return poll_poll(obj, 'ambiance')
def poll_navpaths(group, obj: bpy.types.Object):
    return poll_poll(obj, 'navpath')

#Setting up default values for attrs, Apparently this only works for EnumPropertys as other types 
# dont accept a  function on the default parameter, kind of inconsistent if you ask me
# i dont want to store a seperate variable for each prop as the props are enough (not using get and set)

flavors = {
    "default" : [
        ("none", "None", "There is no flavor and it will not be generated (may as well uncheck this in the Add/Remove Attributes list)")
      ],
    "mudokon" : [
        ("worker","Scrub","The mudokon worker (best for scrubbing floors)"),
        ("native","Lazy Mudokon","A Lazy mud always sitting around not doing much"),
        ("tomohawker","Tomohawker","These guys carry around a large club, dont let 'em near ya"),
        ("archer","Archer","These guys shoot blue darts at people, approach with caution"),
        ("shaman","Shaman","Some dude who cant stop yappin'"),
        ("abe","Abe","We dont know who this guy is, sorta just appeared outa nowhere and started causin' chaos")
      ],
    "munch" : [
        ("munch", "Munch", "This is Munch the gabbit")
      ],
    "bigbro" : [
        ("bigbro","bigbro","Him and his big weapon are definatly compensating for something")
      ],
    "slig" : [
        ("slig", "Slig", "A slig, he sleeps, patrols, shoots and... sleeps. (contains trace amounts of BS)")
      ],
    "fuzzle" : [
        ("fuzzle", "Fuzzle", "Cute with pointy sharp teeth")
      ],
    "paramite" : [
        ("paramite", "Paramite", "One can be fun, two better run... well that aged poorly. None can be fun, Any better Run.")
      ],
    "scrab" : [
        ("scrab", "Scrab", "Not Quite as terratorial as they once were. pretty cosey with each other")
      ],
    "meep" : [
        ("meep", "Meep", "A one eyed one legged ball of fluff. Rare golden variant pending.")
      ],
    "slog" : [
        ("slog", "Slog", "Slog. Hes a goo- no the best boy. (When he's not biting ya legs off)")
      ],
    "glukkon" : [
        ("glukkon", "Glukkon", "The civilized Folk."),
      ],
    "intern" : [
        ("intern", "Intern", "This guy works his ass off and all he gets is his sweet jams")
      ],
    "vykker" : [
        ("vykker", "Vykker", "The humble vykker")
      ],
    "candystriper" : [
        ("candystriper", "Snoozer", "A walking tin can witha a gun and a zap stick. perfec for intimidating unruly slav-*cough*... employees (smiles in glukkon)")
      ],
    "hcrane" : [
        ("hcrane", "Crane", "A Crane")
      ],
  }


defflav = [
]

for flavs in flavors.values():
    for flav in flavs:
        defflav.append(flav)

flavors["default"].extend(defflav)

states = {
    "door" : [
        ("closed", "Closed", "The door is closed"),
        ("open", "Open", "The door is open")
      ],
    "well" : [
        ("closed", "Closed", "The well is closed"),
        ("open", "Open", "The well is open")
      ],
    "lever360" : [
        ("off", "Off", "The lever is in the off state"),
        ("on", "On", "The lever is in the on state")
      ],
    "default" : [
        ("none", "None", "There is no state and it will not be generated (may as well uncheck this in the Add/Remove Attributes list)")
      ],
    "lamp" : [
        ("off", "Unlit", "The lamp is not lit"),
        ("on", "Lit", "The lamp is lit"),
      ]
  }

for state in states.items():
    if state[0] == "default": break
    for s in state[1]:
        states["default"].append(s)

styles = {
    "lamp" : [
        ("triangular", "Triangular", ""),
        ("circular", "Circular", "")  
      ],
    "well" : [
        ("launcher", "Launcher", ""),
        ("transporter", "Transporter", ""),
        ("blowhole", "Blowhole", ""),
      ],
    "default" : [
        ("none", "None", "There is no style and it will not be generated (may as well uncheck this in the Add/Remove Attributes list)")
      ]
  }
for style in styles.items():
    if style[0] == "default": break
    for s in style[1]:
        styles["default"].append(s)

spawntypes = {
    "possessor" : [
        ("later","later","Generated from Real Data"),
        ("now","now","Generated from Real Data")
      ],
    "default" : [
        ("now","now","Generated from Real Data"),
        ("later","later","Generated from Real Data")
      ]
  }



allegiances = {}
# because of different defaults based on type
AddToDict( allegiances, ["paramite","scrab", "default"],  [
        ("neutral","Neutral","Found in TagTemplate"),
        ("native","native","Generated from Real Data"),
        ("slave","slave","Generated from Real Data"),
        ("civilized","Civilized","Found in TagTemplate")
    ])
AddToDict( allegiances, ["glukkon","slig", "bigbro"],  [
        ("civilized","Civilized","Found in TagTemplate"),
        ("neutral","Neutral","Found in TagTemplate"),
        ("native","native","Generated from Real Data"),
        ("slave","slave","Generated from Real Data")
    ])
AddToDict( allegiances, ["mudokon"],  [
        ("slave","slave","Generated from Real Data"),
        ("neutral","Neutral","Found in TagTemplate"),
        ("native","native","Generated from Real Data"),
        ("civilized","Civilized","Found in TagTemplate")
    ])
AddToDict( allegiances, ["munch", "fuzzle", "shaman", "possessor"],  [
        ("native","native","Generated from Real Data"),
        ("neutral","Neutral","Found in TagTemplate"),
        ("slave","slave","Generated from Real Data"),
        ("civilized","Civilized","Found in TagTemplate")
    ])

def update_mesh(context):
    obj = context.object
    obj.XinMeshController.update_mesh(context)

allow_update = True
class MeshController:
    def update_mesh(self, context):
        global allow_update, HudLightMaterialsFixed
        if not allow_update: return
        obj = context.object
        print(f"UPDATE MESH")
        match(obj.XinTagType):
            case "actor":
                print("is actor")
                # will always use the first found animation as mesh so if extra animations; they are ignored
                # handle animation specific meshes for the hardcoded animation sets
                pg = obj.XinActor
                if   pg.has_mudokonanimation:
                    if pg.abe == True:
                        SelectObject(obj)
                        obj.data = bpy.data.meshes[f"mud_abe"]
                    else:
                        obj.XinComponentMudokonAnimation.update_mesh(context)
                elif pg.has_munchanimation:
                    obj.XinComponentMunchAnimation.update_mesh(context)
                elif pg.has_fuzzleanimation:
                    obj.XinComponentFuzzleAnimation.update_mesh(context)
                elif pg.has_paramiteanimation:
                    obj.XinComponentParamiteAnimation.update_mesh(context)
                elif pg.has_scrabanimation:
                    obj.XinComponentScrabAnimation.update_mesh(context)
                elif pg.has_meepanimation:
                    obj.XinComponentMeepAnimation.update_mesh(context)
                elif pg.has_sloganimation:
                    obj.XinComponentSlogAnimation.update_mesh(context)
                elif pg.has_bigbroanimation:
                    obj.XinComponentBigBroAnimation.update_mesh(context)
                elif pg.has_sliganimation:
                    obj.XinComponentSligAnimation.update_mesh(context)
                elif pg.has_glukkonanimation:
                    obj.XinComponentGlukkonAnimation.update_mesh(context)
                elif pg.has_internanimation:
                    obj.XinComponentInternAnimation.update_mesh(context)
                elif pg.has_vykkeranimation:
                    obj.XinComponentVykkerAnimation.update_mesh(context)
                elif pg.has_candystriperanimation:
                    obj.XinComponentCandyStriperAnimation.update_mesh(context)
                elif pg.has_lever360animation:
                    obj.XinComponentLever360Animation.update_mesh(context)
                elif pg.has_vendingmachineanimation:
                    print("has vend anim")
                    obj.XinComponentVendingMachineAnimation.update_mesh(context)
                elif pg.has_footswitchanimation:
                    obj.XinComponentFootSwitchAnimation.update_mesh(context)
                elif pg.has_dooranimation:
                    obj.XinComponentDoorAnimation.update_mesh(context)
                elif pg.has_teleporteranimation:
                    obj.XinComponentTeleporterAnimation.update_mesh(context)
                elif pg.has_wheelchairanimation:
                    obj.XinComponentWheelchairAnimation.update_mesh(context)
                elif pg.has_recycleranimation:
                    obj.XinComponentRecyclerAnimation.update_mesh(context)
                # handle hardcoded meshes, like wells witch dont have an animation component and so have a predefined hard coded mesh
                elif pg.type == "well":
                    load_markers( "well_markers",[
                        ("civ_well_launcher", "markers/mechanics/well/xcmet-00wel01_bv/xcmet-00wel01_bv.obj"),
                        ("civ_well_transporter", "markers/mechanics/well/xcmet-00wel02_bv/xcmet-00wel02_bv.obj"),
                        ("civ_well_blowhole", "markers/mechanics/well/xcmet-00wwe01_bv/xcmet-00wwe01_bv.obj"),
                        ("nat_well_launcher", "markers/mechanics/well/xnmet-00wel02_bv/xnmet-00wel02_bv.obj"),
                        ("nat_well_transporter", "markers/mechanics/well/xnmet-00wel02_bv/xnmet-00wel02_bv.obj"),
                        ("nat_well_blowhole", "markers/mechanics/well/xnmet-00wwe01_bv/xnmet-00wwe01_bv.obj"),
                    ])
                    SelectObject(obj)
                    dataname = "civ_well_" if pg.breed == "civilized" else "nat_well_"
                    dataname += pg.style
                    obj.data = bpy.data.meshes[dataname]
                    
                    set_modifier_node_group(obj, None)
                    if pg.style == "blowhole":
                        set_modifier_node_group(obj, "WELL", "WellBlowhole")
                    else:
                        set_modifier_node_group(obj, "WELL", "Well")
                    
                    set_modifier_socket(obj, "WELL", "Open", 1.0 if pg.state == "open" else 0.0, False)
                    
                    if pg.breed == "civilized":
                        if pg.style=="blowhole":
                            set_modifier_socket(obj, "WELL", "Frame", "waterwell-civ", True)
                            set_modifier_socket(obj, "WELL", "Glow", "detail01", True)
                        else:
                            set_modifier_socket(obj, "WELL", "Frame", "well-launcher-civ", True)
                            set_modifier_socket(obj, "WELL", "Glow", "lip-glow", True)
                    else:
                        if pg.style=="blowhole":
                            set_modifier_socket(obj, "WELL", "Frame", "Nat_well_water", True)
                        else:
                            set_modifier_socket(obj, "WELL", "Frame", "nat_well_trans", True)
                        set_modifier_socket(obj, "WELL", "Glow", False, False)
                    
                    set_modifier_socket(obj, "WELL", "Blackhole", "blackhole", True)
                    set_modifier_socket(obj, "WELL", "Segment 1", "irispart01", True)
                    set_modifier_socket(obj, "WELL", "Segment 2", "irispart02", True)
                    set_modifier_socket(obj, "WELL", "Segment 3", "irispart03", True)
                    set_modifier_socket(obj, "WELL", "Segment 4", "irispart04", True)
                    set_modifier_socket(obj, "WELL", "Segment 5", "irispart05", True)
                elif pg.type == "landmine":
                    GR = bpy.context.scene.XinMO_Folder.gameroot
                    if not os.path.exists(f"{GR}/{pg.filename[5:]}"): return

                    fn = pg.filename.replace('\\','/').split('/')[-1].split('.')[0]
                    if not os.path.exists(f"{GR}/editor/markers/{pg.filename[5:-4]}/{fn}.obj"):
                        # srcNIF, outFolder, gameroot
                        outFolder = f"{GR}/editor/markers/{pg.filename[5:-4]}"
                        CreateFolder(outFolder)
                        LoadAndExportModel(
                                srcNIF=f"{GR}/{pg.filename[5:]}", 
                                outFolder=outFolder,
                                gameroot=GR
                            )
                    load_markers("landmine_markers", [
                        ("landmine", f"markers/{pg.filename[5:-4]}/{fn}.obj")
                    ])
                    set_mesh(obj, "landmine")
                    set_modifier_node_group(obj, None)
                elif pg.type == "tetheredmine":
                    load_markers("tetheredmine_markers", [
                        ("tetheredmine", "markers/mechanics/mines/xcmet-00tmi01_bv/xcmet-00tmi01_bv.obj")
                    ])
                    set_mesh(obj, "tetheredmine")
                    set_modifier_node_group(obj, None)
                # handle other meshes
                elif pg.type == "ladder":
                    
                    load_markers("ladder_markers",[
                        ("ladder", "markers/assets/ladder/ladder.obj")
                    ])
                    if not obj.data.name == "ladder":
                        set_mesh(obj, "ladder")
                        SelectObject(obj)
                        set_modifier_node_group(obj, None)
                        set_modifier_node_group(obj, "LADDER", "Ladder")
                        set_material(obj, 0, "LadderRungs")
                        set_material(obj, 1, "LadderRungsEdge")
                        set_material(obj, 2, "LadderHandGrips")
                        set_material(obj, 3, "MudStandhere")
                    
                    set_modifier_socket(obj, "LADDER", "HeightVerts", "HeightVerts", True)
                    set_modifier_socket(obj, "LADDER", "Height", pg.height, False)
                    set_modifier_socket(obj, "LADDER", "WidthL", "WidthL", True)
                    set_modifier_socket(obj, "LADDER", "WidthR", "WidthR", True)
                    set_modifier_socket(obj, "LADDER", "WidthCenter", "WidthCenter", True)
                    set_modifier_socket(obj, "LADDER", "Remaining", "Remaining", True)
                    set_modifier_socket(obj, "LADDER", "Width", pg.width, False)
                elif pg.type == "rescueportal":
                    load_markers("rescueportal_markers",[
                        ("rescueportal", "markers/mechanics/rescueportal/rescueportal_base.obj")
                    ])
                    set_mesh(obj, "rescueportal")
                    
                    SelectObject(obj)
                    
                    set_modifier_node_group(obj, None)
                elif pg.type == "nest": 
                    load_markers("nest_markers", [
                        ("resetnest", "markers/mechanics/reset_nest/xnmet-00rne01_bv/xnmet-00rne01_bv.obj")
                    ])
                    
                    set_mesh(obj, "resetnest")
                    
                    SelectObject(obj)
                    
                    set_modifier_node_group(obj, None)
                elif pg.type == "humshrub":
                    load_markers("humshrub_markers", [
                        ("humshrub_Grown", "markers/mechanics/humshrubs/xumet-00hum01/xumet-00hum01.obj"),
                        ("humshrub_Not Grown", "markers/mechanics/humshrubs/xnmet-00hfl01/xnmet-00hfl01.obj"),
                        ("humshrub_Dead", "markers/mechanics/humshrubs/xnmet-00hfd01/xnmet-00hfd01.obj")
                    ])
                    
                    set_mesh(obj, f"humshrub_{obj.XinComponentCollectable.initialstate}")
                    
                    SelectObject(obj)
                    
                    set_modifier_node_group(obj, None)
                elif pg.type == "assetlock":
                    #if pg.multidisplayguid == None: return
                    
                    load_markers("assetlock_markers", [
                        ("assetlock", "markers/mechanics/asset_lock/assetlock_marker/assetlock_marker.obj")
                    ])

                    set_mesh(obj, "assetlock")
                    
                    set_modifier_node_group(obj, None)
                    #SelectObject(obj)
                    
                    # Asset locks do not by default have a mesh
                    # instead they have a pointer to the multidisplayguid
                    # which is a genericobject type with a simpleanimation component and several textdisplays
                    # this is where the mesh is loaded
                    # be it if the assetlock is a component or an actor this is always true
                elif pg.type == "patrolpoint":
                    load_markers("patrolpoint_markers",[
                        ("patrol_point", "markers/mechanics/patrol_point/patrolpoint/patrolpoint.obj")
                    ])
                    set_mesh(obj, "patrol_point")
                    
                    set_modifier_node_group(obj, None)
                elif pg.type == "spawner":
                    load_markers("spawner_markers",[
                        ("spawner", "markers/mechanics/spawner/spawner.obj")
                    ]),
                    bpy.data.materials["Spawner"].blend_method = "BLEND"
                    bpy.data.materials["Spawner"].use_backface_culling = True
                    set_mesh(obj, "spawner")
                    bpy.context.object.material_slots[0].material = bpy.data.materials["Spawner"]
                    
                    set_modifier_node_group(obj, None)
                elif pg.type == "hcrane":
                    add_simple_marker("hcrane", "hcrane", bpy.ops.mesh.primitive_plane_add)
                    
                    if not obj.data.name == "hcrane":
                        set_mesh(obj, "hcrane")
                        SelectObject(obj)
                        set_modifier_node_group(obj, None) # clears
                        set_modifier_node_group(obj, "CRANE", "hcrane")
                        add_modifier(obj, "WIREFRAME", "WIREFRAME")
                    
                    set_modifier_socket(obj, "CRANE", "width", pg.width, False)
                    set_modifier_socket(obj, "CRANE", "height", pg.height, False)
                    set_modifier_socket(obj, "CRANE", "offsetX", pg.xoffset, False)
                    set_modifier_socket(obj, "CRANE", "offsetY", pg.yoffset, False)
                    
                    obj.modifiers["WIREFRAME"].thickness = 5
                    obj.modifiers["WIREFRAME"].offset = 0
                    obj.modifiers["WIREFRAME"].use_boundary = True
                # TODO: WATER
                elif pg.type == "lamp":
                    load_markers("lamp_maprkers", [
                        ("civ_tri_lamp", "markers/mechanics/door/xcmet-00hdl01_bv/xcmet-00hdl01_bv.obj"),
                        ("civ_cir_lamp", "markers/mechanics/door/xcmet-00hdl02_bv/xcmet-00hdl02_bv.obj"),
                        ("nat_tri_lamp", "markers/mechanics/door/xnmet-00hdl01_bv/xnmet-00hdl01_bv.obj"),
                        ("nat_cir_lamp", "markers/mechanics/door/xnmet-00hdl02_bv/xnmet-00hdl02_bv.obj")
                    ])
                    lst = ["civ_tri_lamp", "civ_cir_lamp", "nat_tri_lamp", "nat_cir_lamp"]
                    HudLightMaterial(bpy.data.meshes["civ_tri_lamp"].materials[0])
                    HudLightMaterial(bpy.data.meshes["civ_cir_lamp"].materials[1])
                    HudLightMaterial(bpy.data.meshes["nat_tri_lamp"].materials[1])
                    HudLightMaterial(bpy.data.meshes["nat_cir_lamp"].materials[1])

                    prefix1 = "civ" if pg.breed == "civilized" else "nat"
                    prefix2 = "cir" if pg.style == "circular" else "tri"
                    set_mesh(obj, f"{prefix1}_{prefix2}_lamp")
                    SelectObject(obj)
                    set_modifier_node_group(obj, None)
                    
                    obj["lamp_on"] = 1 if pg.state == "on" else 0
                elif pg.type == "deathtag":
                    load_markers("deathtag_markers", [
                        ("loading_chute", "markers/assets/loadingchute/loadingchute.obj")
                    ])
                
                #elif pg.type == "hcranepanel":
                #    allow_update = False
                #    obj.XinComponentSimpleAnimation.filename = "./../Mechanics/Munch_Control_Panel/ncmet-00cpo01_bv.nif"
                #    allow_update = True
                #    obj.XinComponentSimpleAnimation.update_mesh(context)
                #elif pg.type == "shamancircle":
                #    allow_update = False
                #    obj.XinComponentSimpleAnimation.filename = "./../effects/shaman_circle/shaman_circle.nif"
                #    allow_update = True
                #    obj.XinComponentSimpleAnimation.update_mesh(context)
                #elif pg.type == "touchstone":
                #    obj.XinComponentSimpleAnimation.update_mesh(context)
                #elif pg.type == "resurrectiontotem":
                #    obj.XinComponentSimpleAnimation.update_mesh(context)
                    
                # we do simple anims last as to ensure type based meshes have priority
                elif pg.has_simpleanimation:
                    obj.XinComponentSimpleAnimation.update_mesh(context)
                    
                    
                    pass
                    # if filename exists:
                    #   1 validate it is a nif
                    #   2 check if an object is already present that represents 
                    #      this filename, if so skip to step 6
                    #   3 parse the nif
                    #   4 extract meshes and textures and build an obj and mtl file
                    #   5 load this new object file into the scene in the Markers_Objects_DO_NOT_EDIT/external collection
                    #   6 set the object data to the new objects data
                    # HOWEVER
                elif pg.has_nullanimation:
                    print("NULL ANIM DETECTED")
                    obj.XinComponentNullAnimation.update_mesh(context)
                    pass
            case "waypoint":
                pass
            case "camera":
                pass
            case "cameratransition":
                pg = obj.XinCameraTransition
                add_simple_marker("cameratransition", "cameratransition", bpy.ops.mesh.primitive_plane_add)
                
                if not obj.data.name == "cameratransition":
                    print("Switching to cameratransition")
                    set_mesh(obj, "cameratransition")
                    SelectObject(obj)
                    set_modifier_node_group(obj, None)
                    set_modifier_node_group(obj, "CAMERATRANSITION", "CameraTransition")
                
                set_modifier_socket(obj, "CAMERATRANSITION", "width",  pg.width)
                set_modifier_socket(obj, "CAMERATRANSITION", "height", pg.height)
                
            case "scripttrigger":
                pg = obj.XinScriptTrigger
                add_simple_marker("scripttrigger", "scripttrigger", bpy.ops.mesh.primitive_plane_add)
                
                if not obj.data.name == "scripttrigger":
                    print("Switching to scripttrigger")
                    set_mesh(obj, "scripttrigger")
                    SelectObject(obj)
                    set_modifier_node_group(obj, None)
                    set_modifier_node_group(obj, "SCRIPTTRIGGER", "ScriptTrigger")
                
                set_modifier_socket(obj, "SCRIPTTRIGGER", "width",  pg.width)
                set_modifier_socket(obj, "SCRIPTTRIGGER", "height", pg.height)
                
            case "layouttransition":
                pg = obj.XinLayoutTransition
                add_simple_marker("layouttransition", "layouttransition", bpy.ops.mesh.primitive_plane_add)
                
                if not obj.data.name == "layouttransition":
                    print("Switching to layouttransition")
                    set_mesh(obj, "layouttransition")
                    SelectObject(obj)
                    set_modifier_node_group(obj, None)
                    set_modifier_node_group(obj, "LAYOUTTRANSITION", "LayoutTransition")
                
                set_modifier_socket(obj, "LAYOUTTRANSITION", "width",  pg.width)
                set_modifier_socket(obj, "LAYOUTTRANSITION", "height", pg.height)
                pass
            case "ambiance":
                pass
            case "navpath":
                pass
        pass

class ActorPointer(PropertyGroup):
    
    item:   PointerProperty(
        name="", description="",
        type=bpy.types.Object,
        poll=poll_actors)
    
    def draw(self, layout):
        layout.prop(self, "item")
    def generate(self, obj):
        return self.item.XinActor.guid

class ActorPointerList(PropertyGroup):
    
    def update_count(self, context):
        global allow_update
        if not allow_update: return
        # Add until matches the counter
        while(len(self.items) < self.count):
            self.items.add()
        #remove until matches the counter, always removes the element past the point it should stop
        while(len(self.items) > self.count):
            self.items.remove(self.count)
    
    count:  IntProperty(
        name="Actor Count", 
        description="The amount of actors in the list", 
        default=0, min=0, update=update_count)    
    items:  CollectionProperty(
        name="Actor List", 
        description="The list of actors", 
        type=ActorPointer)
    
    def draw(self, layout, label:str=None):
        if not label == None: 
            layout.prop(self, "count", text=label)
        else:
            layout.prop(self, "count")
        box = layout.column(align=True)
        for ap in self.items:
            ap.draw(box)
    def generate(self, obj):
        allitems = [x.generate(obj) for x in self.items]
        res = ""
        for g in allitems:
            res = f"{res},{str(g)}" if len(res) > 0 else str(g)
        return res

class Actor(PropertyGroup):
    """Actor containing all properties and flags to determine conponent tags"""
    
    """ Preset type stuff """


    # if toggled playercontroll then unset any other player controlls
    def playercontroltoggle(self, context):
        if self.playercontrol == True:
            markers = bpy.types.Collection(bpy.data.collections.get("markers")).all_objects

            for obj in markers:
                if obj.name == context.obj.name: continue
                obj.XinActor.playercontrol = False
    
    def get_flavor(self, context):
        return flavors.get(self.type, flavors["default"])
    
    def get_state(self, context):
        return states.get(self.type, states["default"])
    
    def get_style(self, context):
        return styles.get(self.type, styles["default"])

    def get_spawn_type(self, context):
        return spawntypes.get(self.type, spawntypes["default"])

    def get_allegiance(self, context):
        return allegiances.get(self.type, allegiances["default"])

    # needs major rework because its no longer clas independent
    def update_abe(self, context):
        global allow_update
        if not allow_update: return
        obj = context.object
        #LOG(f"change model {obj.name} to {self.variant}", False)
        #SelectObject(obj)
        allow_update = False

        if self.abe == True:
            self.flavor = "abe"
            self.has_doves = True
        else:
            self.flavor = "worker"
            self.has_doves = False
        allow_update = True

        update_mesh(context)
    
    def update_flavor(self, context):
        global allow_update
        if not allow_update: return
        obj = context.object
        allow_update = False
        if self.flavor == "abe":
            self.abe = True
            self.has_doves = True
        else: 
            self.abe = False
            obj.XinComponentMudokonAnimation.variant = "slave" if self.flavor == "worker" else self.flavor
        allow_update = True
        
        update_mesh(context)

    def update_style(self, context):
        global allow_update
        if not allow_update: return
        update_mesh(context)
        
    def update_breed(self, context):
        global allow_update
        if not allow_update: return
        update_mesh(context)
    
    door_modify_amounts = {
        "big" : 0.0025,
        "regular" : 0.05,
        "vykkers" : 0.05,
        "sewer" : 0.05,
    }
    
    def door_modify_open(self, obj):
        current = self.door_modify_get(obj)
        amount = self.door_modify_amounts[obj.XinComponentDoorAnimation.style]
        print(amount)
        set_modifier_socket(obj, "DOOR", "Open", current+amount, False)
        current = self.door_modify_get(obj)
        if current > 1:
            set_modifier_socket(obj, "DOOR", "Open", 1, False)
        pass
    def door_modify_close(self, obj):
        current = self.door_modify_get(obj)
        amount = -self.door_modify_amounts[obj.XinComponentDoorAnimation.style]
        print(amount)
        set_modifier_socket(obj, "DOOR", "Open", current+amount, False)
        current = self.door_modify_get(obj)
        if current < 0:
            set_modifier_socket(obj, "DOOR", "Open", 0, False)
        pass
    def door_modify_get(self, obj):
        socket = get_modifier_socket(obj, "DOOR", "Open")
        return obj.modifiers["DOOR"][socket]
    
    def well_modify_open(self, obj):
        current = self.well_modify_get(obj)
        amount = 0.05
        print(amount)
        set_modifier_socket(obj, "WELL", "Open", current+amount, False)
        current = self.well_modify_get(obj)
        if current > 1:
            set_modifier_socket(obj, "WELL", "Open", 1, False)
        pass
    def well_modify_close(self, obj):
        current = self.well_modify_get(obj)
        amount = -0.05
        print(amount)
        set_modifier_socket(obj, "WELL", "Open", current+amount, False)
        current = self.well_modify_get(obj)
        if current < 0:
            set_modifier_socket(obj, "WELL", "Open", 0, False)
        pass
    def well_modify_get(self, obj):
        socket = get_modifier_socket(obj, "WELL", "Open")
        return obj.modifiers["WELL"][socket]
    
    def update_state(self, context):
        global allow_update
        if not allow_update: return
        if self.type == "door": 
            if self.state == "open":
                vmt_table[context.object.name] = [
                    self.door_modify_open,
                    self.door_modify_get,
                    1, 1,
                    context.object
                ]
            else:
                vmt_table[context.object.name] = [
                    self.door_modify_close,
                    self.door_modify_get,
                    0, -1,
                    context.object
                ]
            return   
        elif self.type == "well": 
            if self.state == "open":
                vmt_table[context.object.name] = [
                    self.well_modify_open,
                    self.well_modify_get,
                    1, 1,
                    context.object
                ]
            else:
                vmt_table[context.object.name] = [
                    self.well_modify_close,
                    self.well_modify_get,
                    0, -1,
                    context.object
                ]
            return 
        update_mesh(context)
        
    
    launchdest_object: PointerProperty(name="Launch Dest object", type=bpy.types.Object)
    def update_has_launchdest(self, context):
        obj = context.object
        if self.has_launchdest:
            self.launchdest_object = bpy.data.objects.new("LAUNCHDEST", bpy.data.meshes["launchdest"])
            bpy.data.collections["MARKERS"].objects.link(self.launchdest_object)
            self.launchdest_object.parent = obj
            self.launchdest_object.XinTagType = "launchdest"
            self.launchdest_object.location.x = self.launchdest[0]
            self.launchdest_object.location.y = self.launchdest[1]
            self.launchdest_object.location.z = self.launchdest[2]
        else:
            #self.launchdest_object = [ob for ob in obj.children if "LAUNCHDEST" == ob.name.split('.')[0]][0]
            if self.launchdest_object != None and bpy.data.objects.get(self.launchdest_object.name) != None:
                bpy.data.objects.remove(self.launchdest_object, do_unlink=True)
        pass
    
    rejectdest_object: PointerProperty(name="Reject Dest object", type=bpy.types.Object)
    def update_has_rejectdest(self, context):
        obj = context.object
        
        if self.has_rejectdest:
            self.rejectdest_object = bpy.data.objects.new("REJECTDEST", bpy.data.meshes["rejectdest"])
            bpy.data.collections["MARKERS"].objects.link(self.rejectdest_object)
            self.rejectdest_object.XinTagType = "rejectdest"
            self.rejectdest_object.parent = obj
            self.rejectdest_object.location.x = self.rejectdest[0]
            self.rejectdest_object.location.y = self.rejectdest[1]
            self.rejectdest_object.location.z = self.rejectdest[2]
        else:
            #self.rejectdest_object = [ob for ob in obj.children if "REJECTDEST" == ob.name.split('.')[0]][0]
            if self.rejectdest_object != None and bpy.data.objects.get(self.rejectdest_object.name) != None:
                bpy.data.objects.remove(self.rejectdest_object, do_unlink=True)
        pass
    
    def update_launchdest(self, context):
        obj = context.object
        if obj.XinTagType == "launchdest" : obj = obj.parent
        if self.launchdest_object == None:
            self.launchdest_object = [ob for ob in obj.children if "LAUNCHDEST" == ob.name.split('.')[0]][0]
        else:
            #self.launchdest = self.launchdest_object.location
            self.launchdest_object.location.x = self.launchdest[0]
            self.launchdest_object.location.y = self.launchdest[1]
            self.launchdest_object.location.z = self.launchdest[2]
    
    def update_rejectdest(self, context):
        obj = context.object
        if obj.XinTagType == "rejectdest" : obj = obj.parent
        if self.rejectdest_object == None:
            self.rejectdest_object = [ob for ob in obj.children if "REJECTDEST" == ob.name.split('.')[0]][0]
        else:
            #self.rejectdest = self.rejectdest_object.location
            self.rejectdest_object.location.x = self.rejectdest[0]
            self.rejectdest_object.location.y = self.rejectdest[1]
            self.rejectdest_object.location.z = self.rejectdest[2]
        self.property_being_updated = False
   
        
    def update_height(self, context):
        global allow_update
        if not allow_update: return
        obj = context.object
        update_mesh(context)
        
    def update_width(self, context):
        global allow_update
        if not allow_update: return
        obj = context.object
        update_mesh(context)
    
    def update_xoffset(self, context):
        global allow_update
        if not allow_update: return
        obj = context.object
        update_mesh(context)
    
    def update_yoffset(self, context):
        global allow_update
        if not allow_update: return
        obj = context.object
        update_mesh(context)
    
    def update_filename(self, context):
        make_path_absolute(self, "filename")
        update_mesh(context)
        
    def update_type(self, context):
        global allow_update
        if not allow_update: return
        obj = context.object
        if self.type == "custom":
            #print(f"CN:{self.customName} LT:{self.lastType}")
            #self.customName = self.lastType
            return
        if self.type == "testall":
            self.customName = "testall"
            self.SetAttrsAndComponent(True)
            return
        if self.type == "none": 
            self.SetAttrsAndComponent(False)
            set_modifier_node_group(obj, None)
            return
        print(f"Updated Type to: {self.type}")
        self.SetAttrsAndComponent(False) # Remove all attributes and components
        allow_update = False
        match(self.type):
            case "resurrectiontotem":
                self.has_prototypeguid = True
                self.has_assetcomponent = True
                self.has_deadlist = True
                self.has_multidisplayguid = True
                self.has_simpleanimation = True
                self.has_zapfx = True 
                self.has_assetlock = True
                self.sparklestream = True 
                obj.XinComponentSimpleAnimation.builtin = "resurrectiontotem"
            case "nest":
                self.has_assetcomponent = True
            case "spawner":
                self.has_active = True
                self.has_position = True
                self.has_rotation = True
                self.has_maxactive = True
                self.has_maxaliveordead = True
                self.has_actorfall = True
                self.has_spawnlist = True
                self.has_maxspawn = True
                self.has_spawndelay = True
                self.has_killifyouhaveto = True
            case "mudokon":
                self.has_flavor = True
                self.has_playercontrol = True
                self.has_abe = True
                self.has_camerafocus = True
                self.has_collidetype = True
                self.has_avoid = True
                self.has_aimat = True
                self.has_canclimb = True
                self.has_allegiance = True
                self.has_spawntype = True
                self.has_spooce = True
                self.has_spoocemax = True
                self.has_mudokonanimation = True
                self.has_legmotion = True
                self.has_mouth = True
                self.has_ear = True
                self.has_carrier = True
                self.has_behavior = True
                self.has_shortgoal = True
                self.has_shadow = True
                self.has_sparklefx = True
                self.has_weapon = True
                self.has_textdisplay = True
                self.has_powersupply = True
            case "munch":
                self.has_flavor = True
                self.has_playercontrol = True
                self.has_camerafocus = True
                self.has_collidetype = True
                self.has_avoid = True
                self.has_aimat = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_health = True
                self.has_healthmax = True
                self.has_spooce = True
                self.has_spoocemax = True
                self.has_munchanimation = True
                self.has_legmotion = True
                self.has_behavior = True
                self.has_shortgoal = True
                self.has_mouth = True
                self.has_ear = True
                self.has_shadow = True
                self.has_sparklefx = True
                self.has_textdisplay = True
                self.has_doves = True
                self.has_zapfx = True
                self.has_sonar = True
                self.has_powersupply = True
            case "meetle":
                self.has_flavor = True
                self.has_playercontrol = True
                self.has_camerafocus = True
                self.has_collidetype = True
                self.has_avoid = True
                self.has_aimat = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_health = True
                self.has_healthmax = True
                self.has_moolah = True
                self.has_moolahmax = True
                self.has_scale = True
                self.has_meetleanimation = True
                self.has_legmotion = True
                self.has_behavior = True
                self.has_carrier = True
                self.has_mouth = True
                self.has_ear = True
                self.has_shortgoal = True
                self.has_possess = True
                self.has_sparklefx = True
                self.has_weapon = True
                self.has_shadow = True
                self.has_textdisplay = True
            case "wheelchair":
                self.has_flavor = True
                self.has_playercontrol = True
                self.has_camerafocus = True
                self.has_collidetype = True
                self.has_avoid = True
                self.has_aimat = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_health = True
                self.has_healthmax = True
                self.has_spooce = True
                self.has_spoocemax = True
                self.has_moolah = True
                self.has_moolahmax = True
                self.has_wheelchairanimation = True
                self.has_legmotion = True
                self.has_carrier = True
                self.has_shortgoal = True
                self.has_behavior = True
                self.has_ear = True
                self.has_shadow = True
            case "slig":
                self.has_flavor = True
                self.has_playercontrol = True
                self.has_camerafocus = True
                self.has_collidetype = True
                self.has_avoid = True
                self.has_aimat = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_moolah = True
                self.has_moolahmax = True
                self.has_sliganimation = True
                self.has_legmotion = True
                self.has_behavior = True
                self.has_carrier = True
                self.has_mouth = True
                self.has_ear = True
                self.has_shortgoal = True
                self.has_possess = True
                self.has_sparklefx = True
                self.has_weapon = True
                self.has_shadow = True
                self.has_textdisplay = True
                self.has_doves = True
                self.has_powersupply = True
            case "bigbro":
                self.has_flavor = True
                self.has_playercontrol = True
                self.has_camerafocus = True
                self.has_collidetype = True
                self.has_avoid = True
                self.has_aimat = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_moolah = True
                self.has_moolahmax = True
                self.has_bigbroanimation = True
                self.has_legmotion = True
                self.has_mouth = True
                self.has_ear = True
                self.has_shortgoal = True
                self.has_behavior = True
                self.has_possess = True
                self.has_sparklefx = True
                self.has_weapon = True
                self.has_shadow = True
                self.has_textdisplay = True
                self.has_doves = True
                self.has_powersupply = True
            case "candystriper":
                self.has_flavor = True
                self.has_playercontrol = True
                self.has_camerafocus = True
                self.has_collidetype = True
                self.has_avoid = True
                self.has_aimat = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_health = True
                self.has_healthmax = True
                self.has_moolah = True
                self.has_moolahmax = True
                self.has_scale = True
                self.has_candystriperanimation = True
                self.has_legmotion = True
                self.has_mouth = True
                self.has_ear = True
                self.has_shortgoal = True
                self.has_behavior = True
                self.has_weapon = True
                self.has_shadow = True
                self.has_textdisplay = True
                self.has_zapfx = True
                self.has_doves = True
            case "slog":
                self.has_flavor = True
                self.has_playercontrol = True
                self.has_camerafocus = True
                self.has_collidetype = True
                self.has_avoid = True
                self.has_aimat = True
                self.has_spawntype = True
                self.has_canclimb = True
                self.has_health = True
                self.has_healthmax = True
                self.has_scale = True
                self.has_sloganimation = True
                self.has_legmotion = True
                self.has_mouth = True
                self.has_ear = True
                self.has_shortgoal = True
                self.has_behavior = True
                self.has_sparklefx = True
                self.has_possess = True
                self.has_doves = True
                self.has_shadow = True
            case "paramite":
                self.has_flavor = True
                self.has_playercontrol = True
                self.has_camerafocus = True
                self.has_collidetype = True
                self.has_avoid = True
                self.has_aimat = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_health = True
                self.has_healthmax = True
                self.has_allegiance = True
                self.has_spooce = True
                self.has_spoocemax = True
                self.has_paramiteanimation = True
                self.has_legmotion = True
                self.has_mouth = True
                self.has_ear = True
                self.has_shortgoal = True
                self.has_behavior = True
                self.has_sparklefx = True
                self.has_possess = True
                self.has_doves = True
                self.has_shadow = True
            case "scrab":
                self.has_flavor = True
                self.has_playercontrol = True
                self.has_camerafocus = True
                self.has_collidetype = True
                self.has_avoid = True
                self.has_aimat = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_health = True
                self.has_healthmax = True
                self.has_allegiance = True
                self.has_spooce = True
                self.has_spoocemax = True
                self.has_scrabanimation = True
                self.has_legmotion = True
                self.has_mouth = True
                self.has_ear = True
                self.has_shortgoal = True
                self.has_behavior = True
                self.has_sparklefx = True
                self.has_possess = True
                self.has_doves = True
            case "intern":
                self.has_flavor = True
                self.has_playercontrol = True
                self.has_camerafocus = True
                self.has_collidetype = True
                self.has_avoid = True
                self.has_aimat = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_moolah = True
                self.has_moolahmax = True
                self.has_scale = True
                self.has_internanimation = True
                self.has_legmotion = True
                self.has_mouth = True
                self.has_ear = True
                self.has_behavior = True
                self.has_shortgoal = True
                self.has_sparklefx = True
                self.has_possess = True
                self.has_weapon = True
                self.has_doves = True
                self.has_shadow = True
                self.has_powersupply = True
            case "glukkon":
                self.has_flavor = True
                self.has_playercontrol = True
                self.has_camerafocus = True
                self.has_collidetype = True
                self.has_avoid = True
                self.has_aimat = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_moolah = True
                self.has_moolahmax = True
                self.has_scale = True
                self.has_glukkonanimation = True
                self.has_legmotion = True
                self.has_mouth = True
                self.has_ear = True
                self.has_behavior = True
                self.has_shortgoal = True
                self.has_sparklefx = True
                self.has_possess = True
                self.has_textdisplay = True
                self.has_doves = True
                self.has_shadow = True
            case "vykker":
                self.has_flavor = True
                self.has_playercontrol = True
                self.has_camerafocus = True
                self.has_collidetype = True
                self.has_avoid = True
                self.has_aimat = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_moolah = True
                self.has_moolahmax = True
                self.has_scale = True
                self.has_vykkeranimation = True
                self.has_legmotion = True
                self.has_behavior = True
                self.has_carrier = True
                self.has_mouth = True
                self.has_ear = True
                self.has_shortgoal = True
                self.has_possess = True
                self.has_sparklefx = True
                self.has_weapon = True
                self.has_shadow = True
                self.has_textdisplay = True
                self.has_doves = True
                self.has_powersupply = True
            case "fuzzle":
                self.has_flavor = True
                self.has_health = True
                self.has_fuzzleanimation = True
                self.has_behavior = True
            case "meep":
                self.has_flavor = True
                self.has_playercontrol = True
                self.has_camerafocus = True
                self.has_collidetype = True
                self.has_avoid = True
                self.has_aimat = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_health = True
                self.has_healthmax = True
                self.has_spooce = True
                self.has_spoocemax = True
                self.has_meepanimation = True
                self.has_legmotion = True
                self.has_mouth = True
                self.has_ear = True
                self.has_behavior = True
                self.has_shortgoal = True
                self.has_shadow = True
            case "possessor":
                self.has_flavor = True
                self.has_playercontrol = True
                self.has_camerafocus = True
                self.has_collidetype = True
                self.has_avoid = True
                self.has_aimat = True
                self.has_canclimb = True
                self.has_allegiance = True
                self.has_spawntype = True
                self.has_health = True
                self.has_healthmax = True
                self.has_spooce = True
                self.has_spoocemax = True
                self.has_simpleanimation = True
                self.has_legmotion = True
                self.has_shortgoal = True
                self.has_sparklefx = True
                self.has_textdisplay = True
                obj.XinComponentSimpleAnimation.filename = "./../characters/possessor/spooceball_bv.nif"
            case "genericobject":
                self.has_flavor = True
                self.has_collidetype = True
                self.has_playercontrol = True
                self.has_camerafocus = True
                self.has_canclimb = True
                self.has_spawntype = True
            case "guardtower":
                self.has_flavor = True
                self.has_collidetype = True
                self.has_zsort = True
                self.has_canclimb = True
                self.has_simpleanimation = True
            case "tree":
                self.has_flavor = True
                self.has_collidetype = True
                self.has_zsort = True
                self.has_canclimb = True
                self.has_simpleanimation = True
            case "camera":
                self.has_camtype = True
                self.has_defcam = True
                self.has_orcam = True
                self.has_obcam = True
                self.has_munchcam = True
                self.has_abecam = True
                self.has_position = True
                self.has_rotation = True
                self.has_lookspeed = True
                self.has_lookheight = True
                self.has_lookdist = True
                self.has_lensfactor = True
                self.has_farclip = True
                self.has_camheight = True
                self.has_followmin = True
                self.has_followmax = True
                self.has_lockheading = True
                self.has_heading = True
                self.has_pitch = True
                self.has_movespeed = True
                self.has_zmovefactor = True
                self.has_jumplookfactor = True
                self.has_jumplookdelay = True
                self.has_noobstructtest = True
                self.has_nocollidetest = True
                self.has_enabledpad = True
                self.has_heightmin = True
                self.has_heightmax = True
                self.has_centerx = True
                self.has_centery = True
                self.has_anchorid = True
                self.has_anchorpos = True
                self.has_relativeanchorz = True
                self.has_fogsetting = True
                self.has_fogdepth = True
                self.has_fogcolor = True
                self.has_bgcolor = True
            case "cameratransition":
                self.has_flavor = True
                self.has_isactive = True
                self.has_position = True
                self.has_rotation = True
                self.has_width = True
                self.has_height = True
                self.has_destcam = True
                self.has_srccam = True
                self.has_cttype = True
                self.has_time = True
                self.has_holdtime = True
                self.has_orientation = True
            case "layouttransition":
                self.has_flavor = True
                self.has_isactive = True
                self.has_position = True
                self.has_rotation = True
                self.has_width = True
                self.has_height = True
                self.has_layout = True
                self.has_destcam = True
                self.has_destpos = True
                self.has_destplayer = True
                self.has_lttype = True
                self.has_orientation = True
            case "scripttrigger":
                self.has_isactive = True
                self.has_position = True
                self.has_rotation = True
                self.has_width = True
                self.has_height = True
                self.has_orientation = True
                self.has_script = True
            case "largeobject":
                self.has_collidetype = True
                self.has_zoffset = True
                self.has_avoid = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_spherephysics = True
                self.has_simpleanimation = True
            case "light":
                self.has_type = True
                self.has_position = True
                self.has_rotation = True
                self.has_cylinderpos = True
                self.has_radius = True
                self.has_height = True
                self.has_direction = True
                self.has_angle = True
                self.has_ambientcolor = True
                self.has_specularcolor = True
                self.has_diffusecolor = True
                self.has_falloff = True
            case "dynamiclight":
                self.has_flavor = True
                self.has_lighttype = True
                self.has_position = True
                self.has_direction = True
                self.has_radius = True
                self.has_width = True
                self.has_height = True
                self.has_depth = True
                self.has_xaxis = True
                self.has_yaxis = True
                self.has_zaxis = True
                self.has_lightshape = True
                self.has_lightdirection = True
                self.has_attenuation = True
                self.has_ambientcolor = True
                self.has_specularcolor = True
                self.has_diffusecolor = True
                self.has_fadedistance = True
                self.has_exclusive = True
                self.has_shadowtype = True
                self.has_shadowdir = True
                self.has_shadowopacity = True
            case "texturelight":
                self.has_flavor = True
                self.has_position = True
                self.has_direction = True
                self.has_radius = True
                self.has_height = True
                self.has_xvelocity = True
                self.has_yvelocity = True
                self.has_scale = True
                self.has_filename = True
                self.has_numfiles = True
                self.has_fps = True
                self.has_additive = True
            case "lever360":
                self.has_actionradius = True
                self.has_levertype = True
                self.has_sound = True
                self.has_state = True
                self.has_ontime = True
                self.has_lever360animation = True
                self.has_broadcaster = True
            case "footswitch":
                self.has_sound = True
                self.has_ondelay = True
                self.has_offdelay = True
                self.has_inverted = True
                self.has_canclimb = True
                self.has_footswitchanimation = True
                self.has_broadcaster = True
            case "door":
                self.has_state = True
                self.has_canclimb = True
                self.has_dooranimation = True
                obj.XinComponentDoorAnimation.set_modifier(context)
            case "lamp":
                self.has_position = True
                self.has_rotation = True
                self.has_state = True
                self.has_style = True
                self.has_breed = True
            case "well":
                self.has_position = True
                self.has_rotation = True
                self.has_state = True
                self.has_launchheight = True
                self.has_style = True
                self.has_breed = True
                self.has_acceptancelist = True
                self.has_launchdest = True
                self.has_rejectheight = True
                self.has_rejectdest = True
                self.has_destguid = True
                self.has_delay = True
                self.has_switchtocam = True
                self.has_hidedecal = True
                self.has_canclimb = True
                self.has_linkactor = True
                self.has_linkcomponent = True
            case "landmine":
                self.has_position = True
                self.has_rotation = True
                self.has_collidetype = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_radius = True
                self.has_filename = True
                self.has_explosion = True
                self.filename = "./../Mechanics/Mines/xcmet-00lmi01_bv.nif"
            case "freefloatingmine":
                self.has_position = True
                self.has_rotation = True
                self.has_collidetype = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_explosion = True
                self.has_floatation = True
            case "tetheredmine":
                self.has_position = True
                self.has_rotation = True
                self.has_collidetype = True
                self.has_stackheight = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_explosion = True
                self.has_floatation = True
            case "vendingmachine":
                self.has_actionradius = True
                self.has_sound = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_aimat = True
                self.has_componentlink = True
                self.has_vendingmachineanimation = True
                self.has_powerup = True
            case "attachmentspawner":
                self.has_vendingmachine = True
                self.has_actionradius = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_scale = True
                self.has_attachmenttype = True
                self.has_power = True
                self.has_damage = True
                self.has_firerate = True
                self.has_possessedfirerate = True
                self.has_clipsize = True
                self.has_possessedclipsize = True
                self.has_lethal = True
                self.has_beatdamage = True
                self.has_aimat = True
                self.has_vendingmachineanimation = True
            case "recycler":
                self.has_collidetype = True
                self.has_turnoffdelay = True
                self.has_radius = True
                self.has_canclimb = True
                self.has_active = True
                self.has_recycleranimation = True
                self.has_broadcaster = True
            case "chantcircle":
                self.has_collidetype = True
                self.has_radius = True
                self.has_canclimb = True
            case "projectile":
                self.has_parentguid = True
                self.has_flavor = True
                self.has_velocity = True
                self.has_mass = True
                self.has_damage = True
                self.has_collidetype = True
                self.has_canclimb = True
                self.has_simpleanimation = True
            case "hcranepanel":
                self.has_actionradius = True
                self.has_canclimb = True
                self.has_hotspotoffset = True
                self.has_zapspotoffset = True
                self.has_simpleanimation = True
                self.has_target = True
                obj.XinComponentSimpleAnimation.builtin = "hcranepanel"
            case "hcrane":
                self.has_flavor = True
                self.has_type = True
                self.has_height = True
                self.has_width = True
                self.has_decel = True
                self.has_xoffset = True
                self.has_yoffset = True
            case "water":
                self.has_collidetype = True
                self.has_filename = True
                self.has_envfilename = True
                self.has_position = True
                self.has_rotation = True
                self.has_minlevel = True
                self.has_maxlevel = True # NOT IMPLIMENTED
                self.has_percentlevel = True
                self.has_healthycolor = True
                self.has_unhealthycolor = True
                self.has_amplitude1 = True
                self.has_xscale1 = True # NOT IMPLIMENTED
                self.has_yscale1 = True # NOT IMPLIMENTED
                self.has_period1 = True # NOT IMPLIMENTED
                self.has_amplitude2 = True
                self.has_xscale2 = True # NOT IMPLIMENTED
                self.has_yscale2 = True # NOT IMPLIMENTED
                self.has_period2 = True # NOT IMPLIMENTED
                self.has_minalpha = True
                self.has_maxalpha = True
                self.has_canclimb = True
            case "current":
                self.has_collidetype = True
                self.has_filename = True
                self.has_position = True
                self.has_rotation = True
                self.has_direction = True
                self.has_size = True
                self.has_falloff = True
                self.has_force = True
                self.has_particles = True
                self.has_water = True
                self.has_canclimb = True
            case "ladder":
                self.has_height = True
                self.has_width = True
                self.has_rotation = True
                self.has_bpheight = True
                self.height = 50 # because i cant use a function in the FloatProperty default param and refuse to use get/set
                self.width = 20.0995
            case "genericparticles":
                self.has_genericparticlesanimation = True
            case "particlegenerator":
                self.has_position = True
                self.has_rotation = True
                self.has_canclimb = True
            case "leglukstogie":
                self.has_canclimb = True
                self.has_simpleanimation = True
            case "stormcircle":
                self.has_canclimb = True
                self.has_simpleanimation = True
            case "waypoint":
                self.has_position = True
                self.has_rotation = True
                self.has_navpaths = True
                self.has_entrypoint = True
            case "crate":
                self.has_flavor = True
                self.has_collidetype = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_aimat = True
                self.has_pickup = True
                self.has_simpleanimation = True
                self.has_simplemotion = True
                self.has_floatation = True
                self.has_explosion = True
            case "hidezone":
                self.has_position = True
                self.has_rotation = True
                self.has_opacity = True
                self.has_threshold = True
            case "patrolpoint":
                self.has_nullanimation = True
            case "humshrub":
                self.has_sound = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_collectable = True
                self.has_cruisecontroller = True
            case "toxicspore":
                self.has_sound = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_collectable = True
            case "moolahbag":
                self.has_sound = True
                self.has_canclimb = True
                self.has_spawntype = True
                self.has_collectable = True
            case "teleporter":
                self.has_destlayout = True
                self.has_destcamera = True
                self.has_destteleporter = True
                self.has_destposition = True
                self.has_isready = True
                self.has_istouchactivated = True
                self.has_multiteleport = True
                self.has_teleporteranimation = True
            case "multiteleporter":
                self.has_direction = True
                self.has_connectedteleporterid = True
                self.has_arrivalspawnerid = True
                self.has_departureradius = True
                self.has_nullanimation = True
            case "chantsuppressor":
                self.has_aimat = True
                self.has_behavior = True
                self.has_shortgoal = True
                self.has_flyingmotion = True
                self.has_simpleanimation = True
                self.has_zapfx = True
                self.has_ear = True
                obj.XinComponentSimpleAnimation.builtin = "normal"
            case "ambiance":
                self.has_position = True
                self.has_radius = True
                self.has_height = True
                self.has_type = True
                self.has_emitoffset = True
                self.has_emitradius = True
                self.has_emitheight = True
                self.has_freqmin = True
                self.has_freqmax = True
            case "rescueportal":
                self.has_actionradius = True
                self.has_collidetype = True
                self.has_position = True
                self.has_rotation = True
                self.has_rewardmin = True
                self.has_rewardmax = True
                self.has_rewardinc = True
                self.has_rewardinc2 = True
                self.has_ballscalemin = True
                self.has_ballscalemax = True
                self.has_ballscalespeed = True
                self.has_mudjumprange = True
                self.has_mudjumpspeed = True
                self.has_fuzjumprange = True
                self.has_fuzjumpspeed = True
                self.has_rescuedelay = True
                self.has_maxopentime = True
                self.has_rescueradius = True
                self.has_rescueheight = True
                self.has_doves = True
                self.has_sparklefx = True
            case "assetlock":
                self.has_buttonradius = True
                self.has_isready = True
                self.has_activation = True
                self.has_assettype = True
                self.has_assetamount = True
                self.has_greetmsg = True
                self.has_lowassetmsg = True
                self.has_notreadymsg = True
                self.has_errordelay = True
                self.has_linkcomponentguid = True
                self.has_partialpayment = True
                self.has_multidisplayguid = True
                self.has_script = True
                self.has_errdisplayguid = True
                self.has_chantradius = True
                self.has_particleoffset = True
                self.has_particlevalue = True
                self.has_nullanimation = True
                self.has_textdisplay = True
                self.has_sparklestream = True
            case "touchstone":
                self.has_actionradius = True
                self.has_hotspotoffset = True
                self.has_linkcomponent = True
                self.has_simpleanimation = True
                self.has_behavior = True
                obj.XinComponentSimpleAnimation.builtin = "civilized"
            case "cage":
                self.has_actionradius = True
                self.has_zapoffset = True
                self.has_aimat = True
                self.has_health = True
                self.has_simpleanimation = True
                self.has_sonarecho = True
                obj.XinComponentSimpleAnimation.builtin = "cage"
            case "shamancircle":
                self.has_simpleanimation = True
                self.has_fadeactor = True
                self.has_detachactor = True
                self.has_behavior = True
                obj.XinComponentSimpleAnimation.builtin = "shamancircle"
            case "deathtag":
                self.has_active = True
                self.has_rescuetheseflavors = True
                self.has_soundfxset = True
            case "lensflare":
                self.has_position = True
                self.has_rotation = True
                self.has_lensflareprefs = True
                self.has_lensflaretype = True
            case "shaman":
                self.has_flavor = True
                self.has_playercontrol = True
                self.has_abe = True
                self.has_camerafocus = True
                self.has_collidetype = True
                self.has_avoid = True
                self.has_aimat = True
                self.has_canclimb = True
                self.has_allegiance = True
                self.has_spawntype = True
                self.has_spooce = True
                self.has_spoocemax = True
                self.has_mudokon = True
                self.has_mudokonanimation = True
                self.has_legmotion = True
                self.has_mouth = True
                self.has_behavior = True
                self.has_shortgoal = True
                self.has_shadow = True
                self.has_fadeactor = True
                self.has_detachactor = True
        #self.lastType = self.type
        self.customName = self.type
        #print(f"LT:{self.lastType} T:{self.type}")
        allow_update = True
        update_mesh(context)
        pass
    
    
    property_being_updated: BoolProperty(
        name="Property Being Updated",
        default = False
    )
    #Item Sets
    
    def SetAttrsAndComponent(self, state):
        self.has_flavor = state
        self.has_camerafocus = state
        self.has_playercontrol = state
        self.has_abe = state
        self.has_allegiance = state
        self.has_assetcomponent = state
        self.has_componentguid = state
        self.has_destcamera = state
        self.has_destlayout = state
        self.has_destteleporter = state
        self.has_collidetype = state
        self.has_pickup = state
        self.has_envfilename = state
        self.has_filename = state
        self.has_healthycolor = state
        self.has_unhealthycolor = state
        self.has_spawntype = state
        self.has_offdelay = state
        self.has_acceptancelist = state
        self.has_breed = state
        self.has_delay = state
        self.has_destguid = state
        self.has_launchheight = state
        self.has_rejectdest = state
        self.has_rejectheight = state
        self.has_state = state
        self.has_style = state
        self.has_switchtocam = state
        self.has_launchdest = state
        self.has_actorfall = state
        self.has_maxactive = state
        self.has_maxspawn = state
        self.has_spawndelay = state
        self.has_spawnlist = state
        self.has_active = state
        self.has_minlevel = state
        self.has_ondelay = state
        self.has_height = state
        self.has_length = state
        self.has_width = state
        self.has_ambientcolor = state
        self.has_diffusecolor = state
        self.has_lightshape = state
        self.has_lighttype = state
        self.has_radius = state
        self.has_isready = state
        self.has_hotspotoffset = state
        self.has_linkcomponent = state
        self.has_levertype = state
        self.has_health = state
        self.has_moolah = state
        self.has_moolahmax = state
        self.has_spooceball = state
        self.has_istouchactivated = state
        self.has_visible = state
        self.has_ontime = state
        self.has_assetamount = state
        self.has_linkcomponentguid = state
        self.has_multidisplayguid = state
        self.has_partialpayment = state
        self.has_script = state
        self.has_spooce = state
        self.has_spoocemax = state
        self.has_buttonradius = state
        self.has_chantradius = state
        self.has_particlevalue = state
        self.has_shadowtype = state
        self.has_percentlevel = state
        self.has_multiteleport = state
        self.has_activation = state
        self.has_lensflaretype = state
        self.has_lightdirection = state
        self.has_xaxis = state
        self.has_yaxis = state
        self.has_zaxis = state
        self.has_killifyouhaveto = state
        self.has_maxaliveordead = state
        self.has_deadlist = state
        self.has_prototypeguid = state
        self.has_greetmsg = state
        self.has_notreadymsg = state
        self.has_direction = state
        self.has_minalpha = state
        self.has_maxalpha = state
        self.has_canclimb = state
        self.has_scale = state
        self.has_xvelocity = state
        self.has_yvelocity = state
        self.has_attenuation = state
        self.has_amplitude = state
        self.has_frequency = state
        self.has_xoffset = state
        self.has_yoffset = state
        self.has_healthmax = state
        self.has_shadowopacity = state
        self.has_specularcolor = state
        self.has_force = state
        self.has_particles = state
        self.has_size = state
        self.has_body = state
        self.has_errdisplayguid = state
        self.has_lowassetmsg = state
        self.has_particleoffset = state
        self.has_errordelay = state
        self.has_exclusive = state
        self.has_componentlink = state
        self.has_rescuetheseflavors = state
        self.has_fadedistance = state
        self.has_divisor = state
        self.has_amplitude1 = state
        self.has_amplitude2 = state
        self.has_countingorder = state
        self.has_droppoint = state
        self.has_turnoffdelay = state
        self.has_bpheight = state
        self.has_inverted = state
        
        self.has_legmotion = state
        self.has_flyingmotion = state
        self.has_simplemotion = state
        self.has_ear = state
        self.has_munchanimation = state
        self.has_mudokonanimation = state
        self.has_simpleanimation = state
        self.has_dooranimation = state
        self.has_teleporteranimation = state
        self.has_sliganimation = state
        self.has_lever360animation = state
        self.has_footswitchanimation = state
        self.has_fuzzleanimation = state
        self.has_vendingmachineanimation = state
        self.has_bigbroanimation = state
        self.has_nullanimation = state
        self.has_glukkonanimation = state
        self.has_wheelchairanimation = state
        self.has_paramiteanimation = state
        self.has_scrabanimation = state
        self.has_genericparticlesanimation = state
        self.has_meepanimation = state
        self.has_internanimation = state
        self.has_sloganimation = state
        self.has_vykkeranimation = state
        self.has_recycleranimation = state
        self.has_candystriperanimation = state
        self.has_behavior = state
        self.has_job = state
        self.has_doves = state
        self.has_zapfx = state
        self.has_assetlock = state
        self.has_sparklestream = state
        self.has_weapon = state
        self.has_broadcaster = state
        self.has_collectable = state
        self.has_powerup = state
        self.has_shadow = state
        self.has_lifecycle = state
        self.has_explosion = state
        self.has_target = state
        self.has_bullseye = state
        self.has_shortgoal = state
        self.has_transformer = state
        self.has_onoffswitch = state
        self.has_attachmentspawner = state
        self.has_floatation = state
        self.has_actortally = state
        self.has_actortally2 = state
        self.has_actortally3 = state
        self.has_actortally4 = state
        self.has_actortally5 = state
        self.has_textdisplay = state
        self.has_textdisplay2 = state
        self.has_textdisplay3 = state
        self.has_textdisplay4 = state
        self.has_textdisplay5 = state
        self.has_textdisplay6 = state
        self.has_textdisplay7 = state
        self.has_textdisplay8 = state
        self.has_textdisplay9 = state
        self.has_textdisplay10 = state
        self.has_textdisplay11 = state
        self.has_textdisplay12 = state
        self.has_textdisplay13 = state
    
    
    lastType = ""
    type: EnumProperty( #note that this is not used in generation its only for deciding a type in the editor and it will be defered by the favor thenforth
        name="Type",
        description="What type of object this is",
        items=[
            ("custom", "Custom", "A Custom actor instead of a preset"),
            ("testall", "===Test All===", "Testing Actor for testing all the attributes"),
            ("none", "===None===", "Testing Actor for clearing the arrt list"),
            ("_sep1","CHARACTERS","Characters that have ai"),
            ("munch","Munch","Munch... the last gabbit."),
            ("fuzzle","Fuzzle","A cute ball of terror"),
            ("mudokon","Mudokon","The main work force of oddworlds industrialists, some would say slaves, but that cant be right... can it?"),
            ("shaman","Shaman","This guy seems to be able to get anywhere... maby he should save oddworld with all his fancy powers"),
            ("paramite","Paramite","The paramite... or at least a close approximation as these guys will attack you on sight even when they are alone, and cant climb"),
            ("scrab","Scrab","The scrab... who knows how they were tamed, but they are not as terratorial as their tribe born cousins, they dont attack one another but will still see you as a free meal."),
            ("meep","Meep","Boing Boing... Meep Sheep goes Baaaaa"),
            ("slog","Slog","These loyal slogos are the sligs best buds and will run right at anyone their masters deem as threats"),
            ("slig","Slig","The main security of the industrialists, although slightly less armed than those in the big factories."),
            ("bigbro","Bigbro","These guys ave only recently been rolled out. They are big and to match that they have a big weapon"),
            ("glukkon","Glukkon","Glukkons come in many sizes... actually just one - Greedy"),
            ("intern","Intern","The main security force of the Vykkers, They guard the labs well and usually the subjects dont escape... usually"),
            ("vykker","Vykker","These guys run Vykkers labs... who'd have guessed, stay outa' their way or you'll end up an experiment or worse"),
            ("candystriper","Snoozer","Made to knock out those pesky test subjects that make it a bit too far... we'll just leave these controlls here, no one gonna mess with them right... right?"),
            ("_sep2","INTERACTABLE","Actors that can be Used or interacted with"),
            ("ladder","Ladder","Its a ladder... you climb it"),
            ("rescueportal","Rescue portal","How did these gent here, are we endorsing the escape of slav-    emplyees."),
            ("lever360","Lever360","Its a lever... You pull it and things happen"),
            ("vendingmachine","Vending machine","Vendos. You can get cool powerups from these tasty drinks. Just stay away from those native knock offs"),
            ("nest","Nest","These Egg Nests will resurrect those guys with plot armor (as long as one of them is alive)"),
            ("humshrub","Humshrub","The source of the spooce energy, powered by nature"),
            ("footswitch","Foot switch","Its a footswitch, you stand on it and things happen, also has a timer attatched for \"convienience\""),
            ("assetlock","Asset lock","Used to keep doors or other things locked"),
            ("hcranepanel","Crane panel","A standard controll panel for various things"),
            ("shamancircle","Shaman circle","Summons that shaman fellow. Dont know how it got here... someone needs to step up security"),
            ("touchstone","Touch stone","Use to get important information. You can also assign scripts to these for custom actions"),
            ("well","Well","Well well well, Not as cool looking as the ones in prior games, these do pretty much the same thing tho"),
            ("resurrectiontotem","Resurrection totem","Generated from Real Data"),
            ("wheelchair","Wheel chair","Munch needs this to move fast on land. Dont know why were helping the gabbits out here"),
            ("crate","Crate","This can be one of three things. Big orange, bone powder or labour eggs"),
            ("landmine","Land mine","Go on, its just waiting to be stepped on"),
            ("tetheredmine","Tethered mine","Placed in water for maximum defence. couldn't possibly be avoided"),
            ("cage","Cage","We keep fuzzles in these"),
            ("recycler","Recycler","Chop Chop. Grinds anything up into its component parts (at least thats what its supposed to be for)"),
            ("_sep3", "SCRIPTABLE", "Objects that are used with scripts or events"),
            ("door","Door","A threshold from one area to another, thats what a door is dummy, can be open or closed :)"),
            ("patrolpoint","Patrol point","used to mark the path of a moving actor"),
            ("chantsuppressor","Chant suppressor","Stop those pesky muds from possesing our guards"),
            ("teleporter","Teleporter","These pads are used for near instant transportation by means of shananigans"),
            ("spawner","Spawner","Spawns the desired actor (will kill it if that flag is checked if that actor is already spawned)"),
            ("hcrane","Crane","Pick things up drop them... we dont place things, what are you stupid."),
            ("water","Water","A plane of water. the height of the water can be ajusted in scripts"),
            ("lamp","Lamp","The lamp is a indicator for unlocking doors (or other things), like spirit locks in exodus"),
            ("_sep4", "ENVIROMENT","Objects that alter the enviroment"),
            ("dynamiclight","Dynamic light","Place these around to make actors have lighting (does not affect layout lighting as that is done with vertex colors)"),
            ("lensflare","Lens flare","Used for light effects in the sun or wherever really"),
            ("texturelight", "Texture Light", "Needs Research"),
            ("genericparticles","Generic particles","Allows for things like the particles aroud fire torches in the rasins cave"),
            ("_sep5","OTHER","Objects used by other parts of the game or are generic"),
            ("genericobject","Generic object","Used for adding custom scenery that doesnt have any real functionality other than visual. can be animated see(region00/splinterz/splinterzwheels.nif you may need to change the header version to [3.3.0.13], use a hex editor; I recomend ImHex )"),
            ("deathtag","Death tag","Mainly used for the Loading Chute Collision"),
            ("possessor","Possessor","The orb that needs to be loaded into the level when abe is able to possess things"),
        ],
        update=update_type,
        default="custom")
    
    customName : StringProperty(
        name="Custom Type Name", 
        description="the name given to the type when this is a custom asset",
        default="")
    
    """ Enumerated Assets """

    
    #Properties
    
    guid: IntProperty(
        name="GUID",
        description="DESCVAL",
        min=0,
        default=0)
    
    # Attribute adders
    # this is the properties that determine if a given attribute exists
    showHasAttr              : BoolProperty(name="Add/Remove Attributes",description="Show the panel to select what attributes this actor has",default=False)
    
    edit_componentguid       : BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
    has_flavor               : BoolProperty(name="Flavor",                 description="", default=False)
    has_camerafocus          : BoolProperty(name="Camera Focus",            description="", default=False)
    has_playercontrol        : BoolProperty(name="Player Control",          description="", default=False)
    has_abe                  : BoolProperty(name="Abe",                    description="", default=False)
    has_allegiance           : BoolProperty(name="Allegiance",             description="", default=False)
    has_assetcomponent       : BoolProperty(name="Asset Component",         description="", default=False)
    has_destcamera           : BoolProperty(name="Dest Camera",             description="", default=False)
    has_destlayout           : BoolProperty(name="Dest Layout",             description="", default=False)
    has_destteleporter       : BoolProperty(name="Dest Teleporter",         description="", default=False)
    has_collidetype          : BoolProperty(name="Collide Type",            description="", default=False)
    has_pickup               : BoolProperty(name="Pickup",                 description="", default=False)
    has_envfilename          : BoolProperty(name="Env File Name",            description="", default=False)
    has_filename             : BoolProperty(name="File Name",               description="", default=False)
    has_healthycolor         : BoolProperty(name="Healthy Color",           description="", default=False)
    has_unhealthycolor       : BoolProperty(name="Unhealthy Color",         description="", default=False)
    has_spawntype            : BoolProperty(name="Spawn Type",              description="", default=False)
    has_offdelay             : BoolProperty(name="Off Delay",               description="", default=False)
    has_acceptancelist       : BoolProperty(name="Acceptance List",         description="", default=False)
    has_breed                : BoolProperty(name="Breed",                  description="", default=False)
    has_delay                : BoolProperty(name="Delay",                  description="", default=False)
    has_destguid             : BoolProperty(name="Dest GUID",               description="", default=False)
    has_launchheight         : BoolProperty(name="Launch Height",           description="", default=False)
    has_rejectdest           : BoolProperty(name="Reject Dest",             description="", default=False, update=update_has_rejectdest)
    has_rejectheight         : BoolProperty(name="Reject Height",           description="", default=False)
    has_state                : BoolProperty(name="State",                  description="", default=False)
    has_style                : BoolProperty(name="Style",                  description="", default=False)
    has_switchtocam          : BoolProperty(name="Switch To Cam",            description="", default=False)
    has_launchdest           : BoolProperty(name="Launch Dest",             description="", default=False, update=update_has_launchdest)
    has_actorfall            : BoolProperty(name="Actor Fall",              description="", default=False)
    has_maxactive            : BoolProperty(name="Max Active",              description="", default=False)
    has_maxspawn             : BoolProperty(name="Max Spawn",               description="", default=False)
    has_spawndelay           : BoolProperty(name="Spawn Delay",             description="", default=False)
    has_spawnlist            : BoolProperty(name="Spawn List",              description="", default=False)
    has_active               : BoolProperty(name="Active",                 description="", default=False)
    has_minlevel             : BoolProperty(name="Min Level",               description="", default=False)
    has_ondelay              : BoolProperty(name="On Delay",                description="", default=False)
    has_height               : BoolProperty(name="Height",                 description="", default=False)
    has_length               : BoolProperty(name="Length",                 description="", default=False)
    has_width                : BoolProperty(name="Width",                  description="", default=False)
    has_ambientcolor         : BoolProperty(name="Ambient Color",           description="", default=False)
    has_diffusecolor         : BoolProperty(name="Diffuse Color",           description="", default=False)
    has_lightshape           : BoolProperty(name="Light Shape",             description="", default=False)
    has_lighttype            : BoolProperty(name="Light Type",              description="", default=False)
    has_radius               : BoolProperty(name="Radius",                 description="", default=False)
    has_isready              : BoolProperty(name="Is Ready",                description="", default=False)
    has_hotspotoffset        : BoolProperty(name="Hot Spot Offset",          description="", default=False)
    has_linkcomponent        : BoolProperty(name="Link Component",          description="", default=False)
    has_levertype            : BoolProperty(name="Lever Type",              description="", default=False)
    has_health               : BoolProperty(name="Health",                 description="", default=False)
    has_moolah               : BoolProperty(name="Moolah",                 description="", default=False)
    has_moolahmax            : BoolProperty(name="Moolah Max",              description="", default=False)
    has_spooceball           : BoolProperty(name="Spooce Ball",             description="", default=False)
    has_istouchactivated     : BoolProperty(name="Is Touch Activated",       description="", default=False)
    has_visible              : BoolProperty(name="Visible",                description="", default=False)
    has_ontime               : BoolProperty(name="On Time",                 description="", default=False)
    has_assetamount          : BoolProperty(name="Asset Amount",            description="", default=False)
    has_linkcomponentguid    : BoolProperty(name="Link Component GUID",      description="", default=False)
    has_multidisplayguid     : BoolProperty(name="Multi Display GUID",       description="", default=False)
    has_partialpayment       : BoolProperty(name="Partial Payment",         description="", default=False)
    has_script               : BoolProperty(name="Script",                 description="", default=False)
    has_spooce               : BoolProperty(name="Spooce",                 description="", default=False)
    has_spoocemax            : BoolProperty(name="Spooce Max",              description="", default=False)
    has_buttonradius         : BoolProperty(name="Button Radius",           description="", default=False)
    has_chantradius          : BoolProperty(name="Chant Radius",            description="", default=False)
    has_particlevalue        : BoolProperty(name="Particle Value",          description="", default=False)
    has_shadowtype           : BoolProperty(name="Shadow Type",             description="", default=False)
    has_percentlevel         : BoolProperty(name="Percent Level",           description="", default=False)
    has_multiteleport        : BoolProperty(name="Multi Teleport",          description="", default=False)
    has_activation           : BoolProperty(name="Activation",             description="", default=False)
    has_lensflaretype        : BoolProperty(name="Lensflare Type",          description="", default=False)
    has_lightdirection       : BoolProperty(name="Light Direction",         description="", default=False)
    has_xaxis                : BoolProperty(name="X Axis",                  description="", default=False)
    has_yaxis                : BoolProperty(name="Y Axis",                  description="", default=False)
    has_zaxis                : BoolProperty(name="Z Axis",                  description="", default=False)
    has_killifyouhaveto      : BoolProperty(name="Kill If You Have To",        description="", default=False)
    has_maxaliveordead       : BoolProperty(name="Max Alive Or Dead",         description="", default=False)
    has_deadlist             : BoolProperty(name="Dead List",               description="", default=False)
    has_prototypeguid        : BoolProperty(name="Prototype GUID",          description="", default=False)
    has_greetmsg             : BoolProperty(name="Greet Message",               description="", default=False)
    has_notreadymsg          : BoolProperty(name="Not Ready Message",            description="", default=False)
    has_direction            : BoolProperty(name="Direction",              description="", default=False)
    has_minalpha             : BoolProperty(name="Min Alpha",               description="", default=False)
    has_maxalpha             : BoolProperty(name="Max Alpha",               description="", default=False)
    has_canclimb             : BoolProperty(name="Can Climb",               description="", default=False)
    has_scale                : BoolProperty(name="Scale",                  description="", default=False)
    has_xvelocity            : BoolProperty(name="X Velocity",              description="", default=False)
    has_yvelocity            : BoolProperty(name="Y Velocity",              description="", default=False)
    has_attenuation          : BoolProperty(name="Attenuation",            description="", default=False)
    has_amplitude            : BoolProperty(name="Amplitude",              description="", default=False)
    has_frequency            : BoolProperty(name="Frequency",              description="", default=False)
    has_xoffset              : BoolProperty(name="X Offset",                description="", default=False)
    has_yoffset              : BoolProperty(name="Y Offset",                description="", default=False)
    has_healthmax            : BoolProperty(name="Health Max",              description="", default=False)
    has_shadowopacity        : BoolProperty(name="Shadow Opacity",          description="", default=False)
    has_specularcolor        : BoolProperty(name="Specular Color",          description="", default=False)
    has_force                : BoolProperty(name="Force",                  description="", default=False)
    has_particles            : BoolProperty(name="Particles",              description="", default=False)
    has_size                 : BoolProperty(name="Size",                   description="", default=False)
    has_body                 : BoolProperty(name="Body",                   description="", default=False)
    has_errdisplayguid       : BoolProperty(name="Err Display GUID",         description="", default=False)
    has_lowassetmsg          : BoolProperty(name="Low Asset Message",            description="", default=False)
    has_particleoffset       : BoolProperty(name="Particle Offset",         description="", default=False)
    has_errordelay           : BoolProperty(name="Error Delay",             description="", default=False)
    has_exclusive            : BoolProperty(name="Exclusive",              description="", default=False)
    has_componentlink        : BoolProperty(name="Component Link",          description="", default=False)
    has_rescuetheseflavors   : BoolProperty(name="Rescue These Flavors",     description="", default=False)
    has_fadedistance         : BoolProperty(name="Fade Distance",           description="", default=False)
    has_divisor              : BoolProperty(name="Divisor",                description="", default=False)
    has_amplitude1           : BoolProperty(name="Amplitude1",             description="", default=False)
    has_amplitude2           : BoolProperty(name="Amplitude2",             description="", default=False)
    has_countingorder        : BoolProperty(name="Counting Order",          description="", default=False)
    has_droppoint            : BoolProperty(name="Drop Point",              description="", default=False)
    has_turnoffdelay         : BoolProperty(name="Turn Off Delay",           description="", default=False)
    has_bpheight             : BoolProperty(name="BP Height",               description="", default=False)
    has_inverted             : BoolProperty(name="Inverted",               description="", default=False)    
    
    componentguid:          IntProperty(
        name="Component GUID",
        description="The identifier of the component",
        default=1)
    flavor:                 EnumProperty(
        name="Flavor",
        description="The Varient of the type selected",
        items=get_flavor,
        update=update_flavor)
    camerafocus:            BoolProperty(
        name="Camera Focus",
        description="Wether the camera is focused on the actor",
        default=False)
    playercontrol:          BoolProperty(
        name="Player Control",
        description="Wether the player has control of this actor",
        default=False)
    abe:                    BoolProperty(
        name="Abe",
        description="Wether the actor is considered abe by the game",
        default=False,
        update=update_abe)
    allegiance:             EnumProperty(
        name="Allegiance",
        description="The Faction the actor has allegiance to",
        items=get_allegiance)
    assetcomponent:         IntProperty(
        name="Asset Component",
        description="The component identifier for the asset in the current actor",
        min=0,
        default=0)
    destcamera:             IntProperty(
        name="Destination Camera",
        description="The GUID for the camera that is considered the destination by the actor (REPLACE WITH ACTOR PICKER)",
        min=0,
        default=0)
    destlayout:             StringProperty(
        name="Destination Layout", subtype="FILE_PATH",
        description="The path to a region file (xrg) (Paths are always reletive to the exe)",
        default="", update=lambda s,c: make_path_absolute(s, 'destlayout'))
    destteleporter:         IntProperty(
        name="Destination Teleporter",
        description="The Identifier of the teleporter that the sender teleporter will send a valid acotor to (REPLACE WITH ACTOR PICKER)",
        min=0,
        default=0)
    collidetype:            IntProperty(
        name="Collide Type",
        description="Determines how the engine handles collision with this object",
        min=0, max=2, # Maby make an enum so its easier to know what this meansd by looking
        default=0)
    pickup:                 EnumProperty(
        name="Pick-up",
        description="This attribute describes what is allowed to pick up this crate.",
        items=[
                ("any","Any","Generated from Real Data"),
                ("crane","Crane","Generated from Real Data"),
                ("none","None","Generated from Real Data")
            ])
    envfilename:            StringProperty(
        name="Enviroment File Name", subtype="FILE_PATH",
        description="The path to an enviroment file or Bitmap(bmp) image (Paths are always reletive to the exe)",
        default="", update=lambda s, c: make_path_absolute(s, "envfilename"))
    filename:               StringProperty(
        name="File Name", subtype="FILE_PATH",
        description="The path to a model file containing a water plane (nif) (Paths are always reletive to the exe)",
        default="", update=update_filename)
    healthycolor:           FloatVectorProperty(
        name="healthy Color",
        description="The Color when the world health is 100",
        subtype="COLOR", min=0, max=1,
        default=(0.0,0.0,0.0))
    unhealthycolor:         FloatVectorProperty(
        name="Unhealthy Color",
        description="The color when the world health is 0",
        subtype="COLOR", min=0, max=1,
        default=(0.0,0.0,0.0))
    spawntype:              EnumProperty(
        name="Spawn Type",
        description="The initial state of the actor",
        items=get_spawn_type
        )
    offdelay:               FloatProperty(
        name="Off Delay",
        description="The delay for a foot switch to deactivate when there is no actor stating on it.",
        min=0,
        default=10)
    acceptancelist:         PointerProperty(
        name="Acceptance List",
        description="The list of Actor Identifiers that are accepted(REPLACE WITH ACTOR PICKER LIST)",
        type=ActorPointerList)
    breed:                  EnumProperty(
        name="Breed",
        description="The breed of the actor (like flavor but different)",
        items=[
            ("native", "Native", ""),
            ("civilized", "Civilized", ""),
        ],
        update=update_breed)
    delay:                  FloatProperty(
        name="Delay",
        description="the Delay before something",
        min=0,
        default=0.0)
    destguid:               PointerProperty(
        name="Destination GUID",
        description="The Actor Identifier considered the destination (REPLACE WITH ACTOR PICKER)",
        type=bpy.types.Object)
    launchheight:           FloatProperty(
        name="Launch height",
        description="The Height a well will launch an actor",
        min=0,
        default=0.0)
    rejectdest:             FloatVectorProperty(
        name="Reject Destination",
        description="The Location a well launches an actor if the actor is rejected",
        subtype="TRANSLATION",
        default=(0.0,0.0,20), step=100,
        update=update_rejectdest)
    rejectheight:           FloatProperty(
        name="Reject height",
        description="The height the well lauches if the actor is rejected",
        min=0,
        default=0.0)
    state:                  EnumProperty(
        name="State",
        description="States: (open, closed) for Doors and wells, (on, off) for Lever360",
        items=get_state,
        update=update_state)
    style:                  EnumProperty(
        name="Style",
        description="Like flavor but different (used by doors)",
        items=get_style,
        update=update_style)
    switchtocam:            PointerProperty(
        name="Swicth To Camera",
        description="The Camera to switch to.",
        type=bpy.types.Object,
        poll=poll_cameras)
    launchdest:             FloatVectorProperty(
        name="Lauch Destination",
        description="The Destination the well launches an actor to",
        subtype="XYZ",
        default=(0.0,0.0,20), step=100,
        update=update_launchdest)
    actorfall:              BoolProperty(
        name="Actor Fall",
        description="(Needs Research)",
        default=False)
    maxactive:              IntProperty(
        name="Max Active",
        description="Needs reasearch",
        min=0,
        default=0)
    maxspawn:               IntProperty(
        name="Max Spawn",
        description="needs Reasearch",
        min=0,
        default=0)
    spawndelay:             FloatProperty(
        name="Spawn Delay",
        description="(Needs Research)",
        min=0,
        default=0.0)
    spawnlist:              PointerProperty(
        name="Spawn list",
        description="The list of actors to spawn",
        type=ActorPointerList)
    active:                 BoolProperty(
        name="Active",
        description="(needs reasearch)",
        default=False)
    minlevel:               IntProperty(
        name="Min Level",
        description="(Needs Research)",
        min=0,
        default=0)
    ondelay:                FloatProperty(
        name="On Delay",
        description="(Needs research)",
        min=0,
        default=0.0)
    height:                 FloatProperty(
        name="Height",
        description="The Height of the Actor",
        min=0,
        default=1,
        update=update_height)
    length:                 FloatProperty(
        name="Length",
        description="The Length of the Actor",
        min=0,
        default=1)
    width:                  FloatProperty(
        name="Width",
        description="The Width of the actor",
        min=0,
        default=1,
        update=update_width)
    ambientcolor:           FloatVectorProperty(
        name="Ambient Color",
        description="Ambient color",
        subtype="COLOR", min=0, max=1,
        default=(0.0,0.0,0.0))
    diffusecolor:           FloatVectorProperty(
        name="Diffuse Color",
        description="Diffuse Color",
        subtype="COLOR", min=0, max=1,
        default=(0.0,0.0,0.0))
    lightshape:             StringProperty(
        name="Light Shape",
        description="The Shape of a Light Volume",
        default="")
    lighttype:              StringProperty(
        name="Light Type",
        description="The Type of the light volume",
        default="")
    radius:                 FloatProperty(
        name="Radius",
        description="The Radius of the light Volume",
        min=0,
        default=1)
    isready:                BoolProperty(
        name="Is Ready",
        description="(Needs Research)",
        default=False)
    hotspotoffset:          FloatProperty(
        name="Hotspot Offset",
        description="(Needs Research)The offset of the hotspot",
        min=0,
        default=0.0)
    linkcomponent:          IntProperty(
        name="Link Component",
        description="Component Identifier of the linked component",
        min=0,
        default=0)
    levertype:              EnumProperty(
        name="Lever Type",
        description="The type of lever (ENUM)",
        items=[
            ("onoff", "Pulse", "Lever sends a pulse on then off as the lever is pulled"),
            ("togglestate", "Toggle", "Lever switches state when it is pulled")
        ],
        default="onoff")
    health:                 IntProperty(
        name="Health",
        description="The health of the actor",
        min=0,
        default=1200)
    moolah:                 IntProperty(
        name="Moolah",
        description="The amount of moolah the actor has",
        min=0,
        default=0)
    moolahmax:              IntProperty(
        name="Moolah Max",
        description="The Max moolah ther actor can hold",
        min=0,
        default=0)
    spooceball:             IntProperty(
        name="Spooce Ball",
        description="The Actor Identifier that represents the Posession Orb (REPLACE WITH ACTOR PICKER)",
        min=0,
        default=0)
    istouchactivated:       BoolProperty(
        name="Is Touch Activated",
        description="(Needs Research)",
        default=False)
    visible:                BoolProperty(
        name="Visible",
        description="(Needs Research)",
        default=False)
    ontime:                 FloatProperty(
        name="On Time",
        description="(Needs Research)",
        min=0,
        default=0.0)
    assetamount:            FloatProperty(
        name="Aasset Amount",
        description="(needs research)The amount of an asset required to open the asset lock (or the current amount)",
        min=0,
        default=0.0)
    linkcomponentguid:      IntProperty(
        name="Link Component GUID",
        description="(needs research)Same as Link Component but used by something else",
        min=0,
        default=0)
    multidisplayguid:       PointerProperty(
        name="Multi-display GUID",
        description="Identifier of the tree actor",
        type=bpy.types.Object,
        poll=poll_actors)
    partialpayment:         BoolProperty(
        name="Partial Payment",
        description="Determines wether or not an asset lock accepts a partial payment or requires the full payment",
        default=False)
    script:                 StringProperty(
        name="Script",
        description="The name of the script to run in the layout folder",
        default="")
    spooce:                 FloatProperty(
        name="Spooce",
        description="The amount of spooce the actor has",
        min=0,
        default=0)
    spoocemax:              FloatProperty(
        name="Spooce Max",
        description="The maximum spooce an actor can hold",
        min=0,
        default=0.0)
    buttonradius:           IntProperty(
        name="Buttom Radius",
        description="The Radius that an actor need to be in to press a button",
        min=0,
        default=0)
    chantradius:            IntProperty(
        name="Chant Radius",
        description="The Radius for chanting to open the portal",
        min=0,
        default=0)
    particlevalue:          FloatProperty(
        name="Particle Value",
        description="(Needs research)",
        min=0,
        default=0.0)
    shadowtype:             StringProperty(
        name="Shadow Type",
        description="The Type of shadow the actor has(ENUM)",
        default="")
    percentlevel:           FloatProperty(
        name="Percent level",
        description="The percentage of water filled",
        min=0,max=1,
        default=1.0)
    multiteleport:          BoolProperty(
        name="Multi-teleport",
        description="Sets if the telpoerter is a multi-teleporter",
        default=False)
    activation:             EnumProperty(
        name="Activateion",
        description="How the asset component is activated",
        items=[
                ("chant","Chant","Generated from Real Data"),
                ("button","Button","Found in Tag Template"),
                ("link","Link","Found in Tag Template")
            ])
    lensflaretype:          EnumProperty(
        name="Lens Flare Type",
        description="The Type of lens flare(ENUM)",
        items=[
                ("Sun","Sun","Generated from Real Data"),
                ("Positional","Positional","Generated from Real Data")
            ])
    lightdirection:         FloatVectorProperty(
        name="Light Direction",
        description="The Direction of a light volume",
        subtype="XYZ",        
        default=(0.0,0.0,0.0))
    xaxis:                  FloatVectorProperty(
        name="X Axis",
        description="seemed unused or more lower level and shouldnt have been exposed",
        subtype="XYZ",        
        default=(0.0,0.0,0.0))
    yaxis:                  FloatVectorProperty(
        name="Y Axis",
        description="seemed unused or more lower level and shouldnt have been exposed",
        subtype="XYZ",       
        default=(0.0,0.0,0.0))
    zaxis:                  FloatVectorProperty(
        name="Z Axis",
        description="seemed unused or more lower level and shouldnt have been exposed",
        subtype="XYZ",        
        default=(0.0,0.0,0.0))
    killifyouhaveto:        BoolProperty(
        name="Kill if you have to",
        description="(needs research)",
        default=False)
    maxaliveordead:         IntProperty(
        name="Max alive or dead",
        description="(needs reseach)",
        min=0,
        default=0)
    deadlist:               PointerProperty(
        name="Dead List",
        description="List of dead actors",
        type=ActorPointerList)
    prototypeguid:          PointerProperty(
        name="Prototype GUID",
        description="The Guid of the actor to respawn",
        type=bpy.types.Object,
        poll=poll_actors)
    greetmsg:               StringProperty(
        name="Greet MSG",
        description="The message to display on an asset lock",
        default="")
    notreadymsg:            StringProperty(
        name="Not ready Message",
        description="The Message to display on an aasset lock when its not ready",
        default="")
    direction:              FloatVectorProperty(
        name="Direction",
        description="The Direction of an actor (similer to rotaion)",
        subtype="XYZ",        min=0.0,
        default=(0.0,0.0,0.0))
    minalpha:               FloatProperty(
        name="Min Alpha",
        description="The Minimum alpha level of a water actor",
        min=0, max=1,
        default=1.0)
    maxalpha:               FloatProperty(
        name="Max Alpha",
        description="The Maximum alpha level of a water actor",
        min=0, max=1,
        default=1.0)
    canclimb:               BoolProperty(
        name="Can Climb",
        description="(does not work)if the actor can 'climb' a slope",
        default=False)
    scale:                  FloatProperty(
        name="The Scale of an actor",
        description="DESCVAL",
        min=0,
        default=0.0)
    xvelocity:              IntProperty(
        name="X Velocity",
        description="DESCVAL",
        min=0,
        default=0)
    yvelocity:              FloatProperty(
        name="Y Velocity",
        description="DESCVAL",
        min=0,
        default=0.0)
    attenuation:            StringProperty(
        name="Attenuation",
        description="DESCVAL",
        default="")
    amplitude:              FloatProperty(
        name="Amplitude",
        description="DESCVAL",
        min=0,
        default=0.0)
    frequency:              FloatProperty(
        name="Frequency",
        description="DESCVAL",
        min=0,
        default=0.0)
    xoffset:                FloatProperty(
        name="X Offset",
        description="Offset used for crane start position (guess)",
        default=0,
        update=update_xoffset)
    yoffset:                FloatProperty(
        name="Y Offset",
        description="Offset used for crane start position (guess)",
        default=0,
        update=update_yoffset)
    healthmax:              IntProperty(
        name="Health Max",
        description="DESCVAL",
        min=0,
        default=0)
    shadowopacity:          FloatProperty(
        name="Shadow Opacity",
        description="DESCVAL",
        min=0,
        default=0.0)
    specularcolor:          FloatVectorProperty(
        name="Specular Color",
        description="DESCVAL",
        subtype="XYZ",        
        default=(0.0,0.0,0.0))
    force:                  FloatProperty(
        name="Force",
        description="DESCVAL",
        min=0,
        default=0.0)
    particles:              IntProperty(
        name="Generic Particles",
        description="DESCVAL",
        min=0,
        default=0)
    size:                   FloatVectorProperty(
        name="Size",
        description="DESCVAL",
        subtype="XYZ",        
        default=(0.0,0.0,0.0))
    body:                   StringProperty(
        name="Body",
        description="DESCVAL",
        default="")
    errdisplayguid:         IntProperty(
        name="Err Display GUID",
        description="DESCVAL",
        min=0,
        default=0)
    lowassetmsg:            StringProperty(
        name="Low Asset Message",
        description="DESCVAL",
        default="")
    particleoffset:         FloatVectorProperty(
        name="Particle Offset",
        description="DESCVAL",
        subtype="XYZ",        
        default=(0.0,0.0,0.0))
    errordelay:             IntProperty(
        name="Error Delay",
        description="DESCVAL",
        min=0,
        default=0)
    exclusive:              StringProperty(
        name="Exclusive",
        description="DESCVAL",
        default="")
    componentlink:          IntProperty(
        name="Component Link",
        description="DESCVAL",
        min=0,
        default=0)
    rescuetheseflavors:     StringProperty(
        name="Rescue These Flavors",
        description="DESCVAL",
        default="")
    fadedistance:           IntProperty(
        name="Fade Distance",
        description="DESCVAL",
        min=0,
        default=0)
    divisor:                IntProperty(
        name="Divisor",
        description="DESCVAL",
        min=0,
        default=0)
    amplitude1:             FloatProperty(
        name="Amplitude 1",
        description="DESCVAL",
        min=0,
        default=0.0)
    amplitude2:             FloatProperty(
        name="Amplitude 2",
        description="DESCVAL",
        min=0,
        default=0.0)
    countingorder:          StringProperty(
        name="Counting Order",
        description="DESCVAL",
        default="")
    droppoint:              FloatVectorProperty(
        name="Drop Point",
        description="DESCVAL",
        subtype="XYZ",        
        default=(0.0,0.0,0.0))
    turnoffdelay:           FloatProperty(
        name="Turn Off Delay",
        description="DESCVAL",
        min=0,
        default=0.0)
    bpheight:               IntProperty(
        name="BP Height",
        description="DESCVAL",
        min=0,
        default=0)
    inverted:               BoolProperty(
        name="Inverted",
        description="DESCVAL",
        default=False)
    
    #GENERATED CLASSES BELOW
    
    #################################################################################################
    #
    # REGARDING EXTRA ANIMATION COMPONENTS WITHIN ANIMATION COMPONENTS
    #
    # Some animation components have an extra component within them of the same name and only 
    # have a rotation attribute.
    # This seems to be Either erronious or a leftover from an older engine verion as removing these
    # extra components changes nothing regarding how the component works. Nor does modifying
    # the rotation attribute within it actually change anything on the tag.
    #
    # As such this script does not support these extra components as they are pointless extra data.
    #
    # The components and the containing files are as follows
    # 
    # region00/gunroom/gunroom.xin
    # - bigbroanimation
    # - sliganimation
    #
    # region00/splinterz/splinterz.xin
    # - simpleanimation
    # - genericparticlesanimation
    # - sliganimation
    #
    # region01/room12/room12.xin
    # - internanimation
    # 
    # The following levels are part of test levels and demo levels
    # 
    # region05/room01/room01_hums.xin
    # region05/room01/room01_scrabs.xin
    # region05/room01/gamestockdemo/gsdemo.xin
    # region05/windmill/windmill.xin
    # - simpleanimation
    # 
    # 
    #
    #################################################################################################
    
    # TODO -- DONE
    # Add componentguid to ALL components and the actor class...
    # This is because loading from a file i want to be able to set that value
    # to what it is in the file because some objects have specific values for this
    # attribute. and it would break if the pointing value was diferent from the 
    # componentguid value of a component just because i loaded it in and auto generated the 
    # cguid instead of actually storing it.
   
    # COMPONENTS
    class LegMotion(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_resetcamera: BoolProperty(name="Reset Camera", description="",default=True)
        has_resetpoint: BoolProperty(name="Reset Point", description="",default=True)
        has_beatdamage: BoolProperty(name="Beat Damage", description="",default=True)
        has_unconscioushealth: BoolProperty(name="Unconscious Health", description="",default=False)
        has_mirrornormalhealth: BoolProperty(name="Mirror Normal Health", description="",default=False)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )

        resetcamera: IntProperty(
            name="Reset Camera", description="",
            default=0
        )

        resetpoint: FloatVectorProperty(
            name="Reset Point", description="",
            subtype="XYZ", default=(0.0,0.0,0.0)
        )

        # beat damages default changes based on type maby set this on type change?
        beatdamage: FloatProperty(
            name="Beat Damage", description="",
            default=30
        )

        unconscioushealth: FloatProperty(
            name="Unconscious Health", description="",
            default=1000
        )

        mirrornormalhealth: BoolProperty(
            name="Mirror Normal Health", description="",
            default=True
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Leg Motion")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_resetcamera")
                box.prop(self, "has_resetpoint")
                box.prop(self, "has_beatdamage")
                box.prop(self, "has_unconscioushealth")
                box.prop(self, "has_mirrornormalhealth")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")          
            if self.has_resetcamera: layout.prop(self, "resetcamera")
            if self.has_resetpoint: layout.prop(self, "resetpoint")
            if self.has_beatdamage: layout.prop(self, "beatdamage")
            if self.has_unconscioushealth: layout.prop(self, "unconscioushealth")
            if self.has_mirrornormalhealth: layout.prop(self, "mirrornormalhealth")

        def generate(self, obj):
            tag = f"<legmotion componentguid='{self.componentguid}' "
            if self.has_resetcamera: tag += f"resetcamera='{self.resetcamera}' "
            if self.has_resetpoint: tag += f"resetpoint='{VECT(self.resetpoint)}' "
            if self.has_beatdamage: tag += f"beatdamage='{self.beatdamage}' "
            if self.has_unconscioushealth: tag += f"unconscioushealth='{self.unconscioushealth}' "
            if self.has_mirrornormalhealth: tag += f"mirrornormalhealth='{self.mirrornormalhealth}' "
            tag += "/>"
            return tag
    class FlyingMotion(PropertyGroup):

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Flying Motion")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  

        def generate(self, obj):
            tag = f"<flyingmotion componentguid='{self.componentguid}' "
            tag += "/>"
            return tag
    class SimpleMotion(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_gravity: BoolProperty(name="Gravity", description="",default=False)
        has_fallspeed: BoolProperty(name="Fall Speed", description="",default=False)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )

        gravity: BoolProperty(
            name="Gravity", description="",
            default=True
        )

        fallspeed: FloatProperty(
            name="Fall Speed", description="",
            default=10
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Simple Motion")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_gravity")
                box.prop(self, "has_fallspeed")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_gravity: layout.prop(self, "gravity")
            if self.has_fallspeed: layout.prop(self, "fallspeed")

        def generate(self, obj):
            tag = f"<simplemotion componentguid='{self.componentguid}' "
            if self.has_gravity: tag += f"gravity='{self.gravity}' "
            if self.has_fallspeed: tag += f"fallspeed='{self.fallspeed}' "
            tag += "/>"
            return tag
    class Ear(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_range: BoolProperty(name="Range", description="",default=False)
        
        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )

        range: FloatProperty(
            name="Range", description="",
            default=150
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Ear")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_range")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_range: layout.prop(self, "range")

        def generate(self, obj):
            tag = f"<ear componentguid='{self.componentguid}' "
            if self.has_range: tag += f"range='{self.range}' "
            tag += "/>"
            return tag
    class MunchAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_flipskinnormals: BoolProperty(name="Flip Skin Normals", description="",default=False)
        has_skinoverride: BoolProperty(name="Skin Override", description="",default=False)

        def update_mesh(self, context):
            obj = context.object
            
            load_markers("gabbit_markers", [
                ("gabbit_munch", "markers/characters/munch/munch_base_bv/munch_base_bv.obj"),
            ])
            
            SelectObject(obj)
            
            obj.data = bpy.data.meshes[f"gabbit_munch"]
            
            set_modifier_node_group(obj, None)
            

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        flipskinnormals: BoolProperty(
            name="Flip Skin Normals", description="",
            default=False
        )

        skinoverride: EnumProperty(
            name="Skin Override", description="",
            items=[("UseDefault","Use Default","Found in TagTemplate")]
        )
        
        

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Munch Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_flipskinnormals")
                box.prop(self, "has_skinoverride")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_flipskinnormals: layout.prop(self, "flipskinnormals")
            if self.has_skinoverride: layout.prop(self, "skinoverride")

        def generate(self, obj):
            tag = f"<munchanimation componentguid='{self.componentguid}' "
            if self.has_flipskinnormals: tag += f"flipskinnormals='{self.flipskinnormals}' "
            if self.has_skinoverride: tag += f"skinoverride='{self.skinoverride}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class MudokonAnimation(PropertyGroup): 
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_variant: BoolProperty(name="Variant", description="",default=True)
        has_flipskinnormals: BoolProperty(name="Flip Skin Normals", description="",default=False)
        has_skinoverride: BoolProperty(name="Skin Override", description="",default=False)
        has_healthoverride: BoolProperty(name="Health Override", description="",default=False)
        has_light: BoolProperty(name="Light", description="",default=True)

        def update_variant(self, context):
            global allow_update
            if not allow_update: return
            obj = context.object
            allow_update = False
            
            obj.XinActor.flavor = "worker" if self.variant == "slave" else self.variant
            
            allow_update = True
            update_mesh(context)


        def update_mesh(self, context):
            obj = context.object
            
            load_markers("mudokon_markers", [
                ("mud_abe", "markers/characters/mudokon/abe_base_bv/abe_base_bv.obj"),
                ("mud_native", "markers/characters/mudokon/mud_nat_bv/mud_nat_bv.obj"),
                ("mud_tomohawker", "markers/characters/mudokon/mud_tom_bv/mud_tom_bv.obj"),
                ("mud_archer", "markers/characters/mudokon/mud_arc_bv/mud_arc_bv.obj"),
                ("mud_slave", "markers/characters/mudokon/mud_sla_bv/mud_sla_bv.obj"),
                ("mud_shaman", "markers/characters/mudokon/mud_sha_bv/mud_sha_bv.obj"),
            ])
            
            SelectObject(obj)
            
            obj.data = bpy.data.meshes[f"mud_{self.variant}"]

            set_modifier_node_group(obj, "SHADOWFIX", "BadShadowFix")
            set_modifier_socket(obj, "SHADOWFIX", "shadow", "shadow*NOSHADOW", True)
    
        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        variant: EnumProperty(
            name="Variant", description="",
            items=[
                ("slave","Slave","Generated from Real Data"),
                ("native","Native","Generated from Real Data"),
                ("tomohawker","Tomohawker","Generated from Real Data"),
                ("archer","Archer","Generated from Real Data"),
                ("shaman","Shaman","Found in TagTemplate")
            ],
            update=update_variant
        )
        
        light: BoolProperty(
            name="Light",description="",
            default=False
        )

        flipskinnormals: BoolProperty(
            name="Flip Skin Normals", description="",
            default=False
        )

        skinoverride: EnumProperty(
            name="Skin Override", description="",
            items=[("UseDefault","Use Default","Found in TagTemplate")]
        )

        healthoverride: IntProperty(
            name="Health Override", description="",
            default=-1
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Mudokon Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_variant")
                box.prop(self, "has_flipskinnormals")
                box.prop(self, "has_skinoverride")
                box.prop(self, "has_healthoverride")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_variant: layout.prop(self, "variant")
            if self.has_light: layout.prop(self, "light")
            if self.has_flipskinnormals: layout.prop(self, "flipskinnormals")
            if self.has_skinoverride: layout.prop(self, "skinoverride")
            if self.has_healthoverride: layout.prop(self, "healthoverride")

        def generate(self, obj):
            tag = f"<mudokonanimation componentguid='{self.componentguid}' "
            if self.has_variant: tag += f"variant='{self.variant}' "
            if self.has_light: tag += f"light='{self.light}' "
            if self.has_flipskinnormals: tag += f"flipskinnormals='{self.flipskinnormals}' "
            if self.has_skinoverride: tag += f"skinoverride='{self.skinoverride}' "
            if self.has_healthoverride: tag += f"healthoverride='{self.healthoverride}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class SimpleAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_filename: BoolProperty(name="Filename", description="",default=True)
        has_modelname: BoolProperty(name="Model Name", description="",default=False)

        def update_mesh(self, context):
            obj = context.object
            GR = bpy.context.scene.XinMO_Folder.gameroot
            if not os.path.exists(f"{GR}/{self.filename[5:]}"): return
            
            fn = self.filename.replace('\\','/').split('/')[-1].split('.')[0]
            if not os.path.exists(f"{GR}/editor/markers/{self.filename[5:-4]}/{fn}.obj"):
                # srcNIF, outFolder, gameroot
                outFolder = f"{GR}/editor/markers/{self.filename[5:-4]}"
                CreateFolder(outFolder)
                LoadAndExportModel(
                        srcNIF=f"{GR}/{self.filename[5:]}", 
                        outFolder=outFolder,
                        gameroot=GR
                    )
            load_markers("simple_markers", [
                (fn, f"markers/{self.filename[5:-4]}/{fn}.obj")
            ])
            
            set_mesh(obj, fn)
            
            set_modifier_node_group(obj, None)
        
        
        
        builtins = {
            "touchstone" : [
                    ("civilized", "Civilized", "The Civilized Touchstone"),
                    ("native", "Native", "The Native Touchstone")
                ],
            "hcranepanel" : [
                    ("hcranepanel", "Munch Control Panel", "Crane and Snoozer Control Panel")
                ],
            "shamancircle" : [
                    ("shamancircle", "Shaman Circle", "That annoying guys spawner")
                ],
            "resurrectiontotem" : [
                    ("resurrectiontotem", "Resurrection Totem", "That thing that brings back the dead...")
                ],
            "crate" : [
                ("bonepowder", "Bone Powder", "Small Red Carriable explosive Crate (made with bones?)"),
                ("explosive", "Explosive", "Tall Orange Explosive crate, move with a crane"),
                ("egg", "Labour Eggs", "Abes unborn brothers, make sure you aim well")
            ],
            "cage" : [
                ("cage", "Cage", "A cage for fuzzles")
            ],
            "chantsuppressor" : [
                ("normal", "Normal", "The Normal Chant Supressor. slaps you on the wrist for chanting"),
                ("glukkon", "Guard", "The super serious; dont come near me supressor. Kills any uninvited guests"),
            ],
            "default" : [("default", "default", "default")]
        }
        
        builtindata = {
            "touchstone" : {
                "civilized" :  ".././mechanics/touchstone/ncmet-00tou01_bv.nif",
                "native" :  ".././mechanics/touchstone/xnmet-00tou01_bv.nif"
            },
            "hcranepanel" : {
                "hcranepanel" :  ".././mechanics/munch_control_panel/ncmet-00cpo01_bv.nif",          
            },
            "shamancircle" : {
                "shamancircle" :  ".././effects/shaman_circle/shaman_circle.nif"
            },
            "resurrectiontotem" : {
                "resurrectiontotem" :  ".././mechanics/resurrection_totem/xnmet-00rto01_bv.nif"
            },
            "crate" : {
                "bonepowder" : "./../Mechanics/Carryables/ncmet-00bpc01_bv.nif",
                "explosive" : "./../mechanics/crates/ncmet-00ect01_bv.nif",
                "egg" : "./../mechanics/egg_crate/ncmet-00ecr01_bv.nif"
            },
            "cage" : {
                "cage" : "./../mechanics/fuzzle_trap/xcmet-00ftr01_bv.nif"
            },
            "chantsuppressor" : {
                "normal" : "./../mechanics/chant_suppressor/ncmet-00csu01.nif",
                "glukkon" : "./../mechanics/chant_suppressor/ncmet-00scs01_bv.nif",
            }
        }
        
        
        def get_builtin(self, context):
            obj = context.object
            if not obj.XinActor.type in self.builtins.keys(): return self.builtins["default"]
            return self.builtins[obj.XinActor.type]
        
        def update_builtin(self, context):
            obj = context.object
            self.filename = self.builtindata[obj.XinActor.type][self.builtin]
        
        def update_filename(self, context):
            make_path_absolute(self, 'filename')
            update_mesh(context)    

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        builtin: EnumProperty(
            name="Built In", description="The objects that the type has built Ins for",
            items=get_builtin,
            update=update_builtin)
        filename: StringProperty(
            name="Filename", description="", 
            default="", subtype="FILE_PATH", 
            update=update_filename
        )

        modelname: StringProperty(
            name="Model Name", description="unused in real data but has entries in the tag template, looks like scenery stuff",
            default=""
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Simple Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_filename")
                box.prop(self, "has_modelname")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_filename: 
                layout.prop(self, "builtin")
                layout.prop(self, "filename")
            if self.has_modelname: layout.prop(self, "modelname")

        def generate(self, obj):
            tag = f"<simpleanimation componentguid='{self.componentguid}' "
            if self.has_filename: tag += f"filename='{self.filename}' "
            if self.has_modelname: tag += f"modelname='{self.modelname}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class DoorAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_breed: BoolProperty(name="Breed", description="",default=True)
        has_style: BoolProperty(name="Style", description="",default=True)
        has_transparent: BoolProperty(name="Transparent", description="",default=True)

        def set_modifier(self, context):
            obj = context.object
            set_modifier_node_group(obj, None)
            set_modifier_node_group(obj, "DOOR")
            match(self.breed):
                case "native":
                    match(self.style):
                        case "regular":
                            set_modifier_node_group(obj, "DOOR", "NatRegularDoor")
                            set_modifier_socket(obj, "DOOR", "Open",              float(obj.XinActor.state == "open"), False)
                            set_modifier_socket(obj, "DOOR", "Hinge Left",        "Object08", True)
                            set_modifier_socket(obj, "DOOR", "Hinge Right",       "Object09", True)
                            set_modifier_socket(obj, "DOOR", "Door Near Left",    "Line10", True)
                            set_modifier_socket(obj, "DOOR", "Door Near Right",   "Line09", True)
                            set_modifier_socket(obj, "DOOR", "Door Far Left",     "Object03", True)
                            set_modifier_socket(obj, "DOOR", "Door Far Right",    "Object02", True)
                            set_modifier_socket(obj, "DOOR", "Hinge Arm Left",    "Object01", True)
                            set_modifier_socket(obj, "DOOR", "Hinge Arm Right",   "Object05", True)
                            set_modifier_socket(obj, "DOOR", "Frame",             "Cylinder11", True)
                            
                        case "big":
                            set_modifier_node_group(obj, "DOOR", "NatBigDoor")
                            set_modifier_socket(obj, "DOOR", "Open",            float(obj.XinActor.state == "open"), False)
                            set_modifier_socket(obj, "DOOR", "Door",            "native_bigdoor_door", True)
                            set_modifier_socket(obj, "DOOR", "Poles",           "native_bigdoor_bars", True)
                            set_modifier_socket(obj, "DOOR", "Static",          "keeptest_basetree_polehole", True)
                            pass
                case "civilized":
                    match(self.style):
                        case "regular":
                            set_modifier_node_group(obj, "DOOR", "CivRegularDoor")
                            set_modifier_socket(obj, "DOOR", "Open",            float(obj.XinActor.state == "open"), False)
                            set_modifier_socket(obj, "DOOR", "Lock",            "lock front01", True)
                            set_modifier_socket(obj, "DOOR", "LockBladeL",      "doorblade lock01", True)
                            set_modifier_socket(obj, "DOOR", "LockBladeR",      "doorblade-lock01", True)
                            set_modifier_socket(obj, "DOOR", "Core",            "core-axel", True)
                            set_modifier_socket(obj, "DOOR", "CoreLock",        "lock cap02", True)
                            set_modifier_socket(obj, "DOOR", "Blade7L",         "blade-l07", True)
                            set_modifier_socket(obj, "DOOR", "Blade1L",         "blade-l01", True)
                            set_modifier_socket(obj, "DOOR", "Blade2L",         "blade-l02", True)
                            set_modifier_socket(obj, "DOOR", "Blade3L",         "blade-l03", True)
                            set_modifier_socket(obj, "DOOR", "Blade4L",         "blade-l04", True)
                            set_modifier_socket(obj, "DOOR", "Blade5L",         "blade-l05", True)
                            set_modifier_socket(obj, "DOOR", "Blade6L",         "blade-l06", True)
                            set_modifier_socket(obj, "DOOR", "Blade7R",         "blade-r07", True)
                            set_modifier_socket(obj, "DOOR", "Blade1R",         "blade-r01", True)
                            set_modifier_socket(obj, "DOOR", "Blade2R",         "blade-r02", True)
                            set_modifier_socket(obj, "DOOR", "Blade3R",         "blade-r03", True)
                            set_modifier_socket(obj, "DOOR", "Blade4R",         "blade-r04", True)
                            set_modifier_socket(obj, "DOOR", "Blade5R",         "blade-r05", True)
                            set_modifier_socket(obj, "DOOR", "Blade6R",         "blade-r06", True)
                            set_modifier_socket(obj, "DOOR", "Frame",           "hazard frame01", True)
                            set_modifier_socket(obj, "DOOR", "FrameInner",      "frame-inside", True)
                            set_modifier_socket(obj, "DOOR", "Base",            "door-base", True)
                            set_modifier_socket(obj, "DOOR", "CoreBase",        "door base cap01", True)
                            pass
                        case "big":
                            set_modifier_node_group(obj, "DOOR", "CivBigDoor")
                            set_modifier_socket(obj, "DOOR", "Open",            float(obj.XinActor.state == "open"), False)
                            set_modifier_socket(obj, "DOOR", "Door Upper",      "bigdoor_UPPER", True)
                            set_modifier_socket(obj, "DOOR", "Door Lower",      "bigdoor_LOWER", True)
                            set_modifier_socket(obj, "DOOR", "Poles",           "bigpipe_bars", True)
                            pass
                        case "vykkers":
                            set_modifier_node_group(obj, "DOOR", "VykkerDoor")
                            set_modifier_socket(obj, "DOOR", "Open",            float(obj.XinActor.state == "open"), False)
                            set_modifier_socket(obj, "DOOR", "DoorL",           "Door-left", True)
                            set_modifier_socket(obj, "DOOR", "DoorR",           "art_door-right", True)
                            set_modifier_socket(obj, "DOOR", "Frame",           "art_VykkerDoorFrame", True)
                            pass
                        case "sewer":
                            set_modifier_node_group(obj, "DOOR", "SewerDoor")
                            set_modifier_socket(obj, "DOOR", "Open",            float(obj.XinActor.state == "open"), False)
                            set_modifier_socket(obj, "DOOR", "Crossbar",        "door_crossbar", True)
                            set_modifier_socket(obj, "DOOR", "Bars1",           "door_bars01", True)
                            set_modifier_socket(obj, "DOOR", "Bars3",           "door_bars03", True)
                            set_modifier_socket(obj, "DOOR", "Bars2",           "door_bars02", True)
                            set_modifier_socket(obj, "DOOR", "Frame",           "doorframe", True)
                            pass

        def update_mesh(self, context):
            global allow_update
            if not allow_update: return
            obj = context.object
            print("Update door mesh")
            load_markers("door_markers", [
                ("door_regular_civilized", "markers/mechanics/door/xcmet-00doo01_bv/xcmet-00doo01_bv.obj"),
                ("door_regular_civilized_i", "markers/mechanics/door/xcmet-00doo02_bv/xcmet-00doo02_bv.obj"),
                ("door_regular_native", "markers/mechanics/door/nnmet-00doo01_bv/nnmet-00doo01_bv.obj"),
                ("door_regular_native_i", "markers/mechanics/door/nnmet-00doo02_bv/nnmet-00doo02_bv.obj"),
                ("door_big_civilized", "markers/mechanics/door/ncmet-00bdo01_bv/ncmet-00bdo01_bv.obj"),
                ("door_big_civilized_i", "markers/mechanics/door/ncmet-00bdo02_bv/ncmet-00bdo02_bv.obj"),
                ("door_big_native", "markers/mechanics/door/bigdoornative_bv/bigdoornative_bv.obj"),
                ("door_big_native_i", "markers/mechanics/door/bigdoornative02_bv/bigdoornative02_bv.obj"),
                ("door_vykkers_civilized", "markers/mechanics/door/ncmet-00vod01_bv/ncmet-00vod01_bv.obj"),
                ("door_sewer_civilized", "markers/mechanics/door/ncmet-00sdo02_bv/ncmet-00sdo02_bv.obj"),
            ])
            
            SelectObject(obj)
            
            path ="door"
            path += f"_{self.style}"
            path += f"_{self.breed}"
            if self.style in ["regular","big"] and self.transparent:
                path += "_i"
            #if  ["regular","big"].__contains__(self.style):
            #    path = f"door_{self.style}_{self.breed}{'_i' if self.transparent else ''}_{'_o' if obj.XinActor.has_state and obj.XinActor.state == 'open' else '' }"
            #else:
            #    path = f"door_{self.style}_civilized" #{'_o' if obj.XinActor.has_state and obj.XinActor.state == 'open' else '' }"
            obj.data = bpy.data.meshes[path]
            self.set_modifier(context)
            
        def breed_update(self, context):
            global allow_update
            if not allow_update: return
            if self.breed == "native" and not self.style in ["regular","big"]:
                self.style = "regular"
            update_mesh(context)

        def style_update(self, context):
            global allow_update
            if not allow_update: return
            if  not self.style in ["regular","big"]:
                self.breed = "civilized"
                self.transparent = False
            update_mesh(context)

        def transparent_update(self, context):
            global allow_update
            if not allow_update: return
            if self.transparent and not self.style in ["regular","big"]:
                self.style = "regular"
            update_mesh(context)
        
        
            
            
        
        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        breed: EnumProperty(
            name="Breed", description="",
            items=[
                ("civilized","civilized","Generated from Real Data"),
                ("native","native","Generated from Real Data")
            ],
            update=breed_update
        )

        style: EnumProperty(
            name="Style", description="",
            items=[
                ("regular","Regular","Found in TagTemplate"),
                ("big","big","Generated from Real Data"),
                ("vykkers","vykkers","Generated from Real Data"),
                ("sewer","sewer","Generated from Real Data"),
                ("hub","Hub","Found in TagTemplate")
            ],
            update=style_update
        )

        transparent: BoolProperty(
            name="Transparent", description="",
            default=False,
            update=transparent_update
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Door Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_breed")
                box.prop(self, "has_style")
                box.prop(self, "has_transparent")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_breed: layout.prop(self, "breed")
            if self.has_style: layout.prop(self, "style")
            if self.has_transparent: layout.prop(self, "transparent")

        def generate(self, obj):
            tag = f"<dooranimation componentguid='{self.componentguid}' "
            if self.has_breed: tag += f"breed='{self.breed}' "
            if self.has_style: tag += f"style='{self.style}' "
            if self.has_transparent: tag += f"transparent='{self.transparent}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class TeleporterAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_breed: BoolProperty(name="Breed", description="",default=True)
        has_invisible: BoolProperty(name="Invisible", description="",default=True)
        has_height: BoolProperty(name="Height", description="",default=True)
        has_radius: BoolProperty(name="Radius", description="",default=True)
        
        def update_breed(self, context):
            global allow_update
            if not allow_update: return
            update_mesh(context)
            pass
        
        def update_mesh(self, context):
            obj = context.object
            # if it hasnt been loaded then load and create the teleporter varients to the blend file
            
            # load_marker(collection, [(name, path)]) paths must be relative to the blend file
            
            load_markers("teleporter_markers", [
                ("tele_nat", "markers/mechanics/teleporter/nnmet-00tel01_bv/nnmet-00tel01_bv.obj"),
                ("tele_nat_a", "markers/mechanics/teleporter/nnmet-00tel01a_bv/nnmet-00tel01a_bv.obj"),
                ("tele_nat_m", "markers/mechanics/teleporter/nnmet-00tel01m_bv/nnmet-00tel01m_bv.obj"),
                ("tele_nat_am", "markers/mechanics/teleporter/nnmet-00tel02_bv/nnmet-00tel02_bv.obj"),
                ("tele_civ", "markers/mechanics/teleporter/ncmet-00tel01_bv/ncmet-00tel01_bv.obj"),
                ("tele_civ_a", "markers/mechanics/teleporter/ncmet-00tel01a_bv/ncmet-00tel01a_bv.obj"),
                ("tele_civ_m", "markers/mechanics/teleporter/ncmet-00tel01m_bv/ncmet-00tel01m_bv.obj"),
                ("tele_civ_am", "markers/mechanics/teleporter/ncmet-00tel02_bv/ncmet-00tel02_bv.obj")
            ])
            
            match(self.breed):
                case "native": 
                    set_mesh(obj, "tele_nat")
                    pass
                case "abe":  
                    set_mesh(obj, "tele_nat_a")
                    pass
                case "munch":  
                    set_mesh(obj, "tele_nat_m")
                    pass
                case "abemunch":  
                    set_mesh(obj, "tele_nat_am")
                    pass
                case "civilized":  
                    set_mesh(obj, "tele_civ")
                    pass
                case "civabe":  
                    set_mesh(obj, "tele_civ_a")
                    pass
                case "civmunch":  
                    set_mesh(obj, "tele_civ_m")
                    pass
                case "civabemunch":  
                    set_mesh(obj, "tele_civ_am")
                    pass
                
            set_modifier_node_group(obj, None)
                
        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        breed: EnumProperty(
            name="Breed", description="",
            items=[
                ("native","Native","Found in TagTemplate"),
                ("abe","Abe","Generated from Real Data"),
                ("munch","Munch","Found in TagTemplate"),
                ("abemunch","Abe Munch","Generated from Real Data"),
                ("civilized","Civilized","Generated from Real Data"),
                ("civabe","Civilized Abe","Generated from Real Data"),
                ("civmunch","Civilized Munch","Found in TagTemplate"),
                ("civabemunch","Civilized Abe Munch","Generated from Real Data")
            ],
            update=update_breed
        )

        invisible: BoolProperty(
            name="Invisible", description="",
            default=False
        )

        height: IntProperty(
            name="Height", description="",
            default=12
        )

        radius: FloatProperty(
            name="Radius", description="",
            default=10
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Teleporter Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_breed")
                box.prop(self, "has_invisible")
                box.prop(self, "has_height")
                box.prop(self, "has_radius")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_breed: layout.prop(self, "breed")
            if self.has_invisible: layout.prop(self, "invisible")
            if self.has_height: layout.prop(self, "height")
            if self.has_radius: layout.prop(self, "radius")

        def generate(self, obj):
            tag = f"<teleporteranimation componentguid='{self.componentguid}' "
            if self.has_breed: tag += f"breed='{self.breed}' "
            if self.has_invisible: tag += f"invisible='{self.invisible}' "
            if self.has_height: tag += f"height='{self.height}' "
            if self.has_radius: tag += f"radius='{self.radius}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class SligAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_preloadclubanims: BoolProperty(name="Preload Club Animations", description="",default=True)
        has_variant: BoolProperty(name="Variant", description="",default=True)
        has_weapontype: BoolProperty(name="Weapon Type", description="",default=True)
        has_preloadgunanims: BoolProperty(name="Preload Gun Animations", description="",default=True)
        has_shieldtype: BoolProperty(name="Shield Type", description="",default=True)
        has_flipskinnormals: BoolProperty(name="Flip Skin Normals", description="",default=False)
        has_healthoverride: BoolProperty(name="Health Override", description="",default=False)
        has_weaponscale: BoolProperty(name="Weapon Scale", description="",default=False)
        has_skinoverride: BoolProperty(name="Skin Override", description="",default=False)

        def update_variant(self, context):
            global allow_update
            if not allow_update: return
            update_mesh(context)
            
        def update_mesh(self, context):
            obj = context.object
            load_markers("slig_markers", [
                ("slig", "markers/characters/slig/slig_bv/slig_bv.obj"),
                ("slig_armor", "markers/characters/slig/slig_armor_bv/slig_armor_bv.obj"),
            ])
            SelectObject(obj)
            
            match(self.variant):
                case "gunsel": 
                    obj.data = bpy.data.meshes["slig"]
                case "clubber":  
                    obj.data = bpy.data.meshes["slig"]
                case "armored":  
                    obj.data = bpy.data.meshes["slig_armor"]

            set_modifier_node_group(obj, None)
            
        
        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        preloadclubanims: BoolProperty(
            name="Preload Club Animations", description="",
            default=False
        )

        variant: EnumProperty(
            name="Variant", description="",
            items=[
                ("gunsel","gunsel","Generated from Real Data"),
                ("clubber","clubber","Generated from Real Data"),
                ("armored","armored","Generated from Real Data")
            ],
            update=update_variant
        )

        weapontype: EnumProperty(
            name="Weapon Type", description="",
            items=[
                ("UseDefault","UseDefault","Generated from Real Data"),
                ("NotAttached","NotAttached","Generated from Real Data"),
                ("SligGun","SligGun","Generated from Real Data"),
                ("SligClub","SligClub","Generated from Real Data"),
                ("BrewGun","BrewGun","Generated from Real Data"),
                ("DrugGun", "DrugGun", "Found in TagTemplate"),
                ("CrossBow", "CrossBow", "Found in TagTemplate"),
                ("ShockRod", "ShockRod", "Found in TagTemplate"),
                ("Saw", "Saw", "Found in TagTemplate")
            ]
        )

        preloadgunanims: BoolProperty(
            name="Preload Gun Animations", description="",
            default=False
        )

        shieldtype: EnumProperty(
            name="Shield Type", description="",
            items=[
                ("UseDefault", "UseDefault", "Found in TagTemplate"),
                ("NotAttached","NotAttached","Generated from Real Data"),
                ("StandardShield", "StandardShield", "Found in TagTemplate")
            ]
        )

        flipskinnormals: BoolProperty(
            name="Flip Skin Normals", description="",
            default=False
        )

        healthoverride: IntProperty(
            name="Health Override", description="",
            default=-1
        )

        weaponscale: FloatProperty(
            name="Weapon Scale", description="",
            default=1
        )

        skinoverride: EnumProperty(
            name="Skin Override", description="",
            items=[("UseDefault","Use Default","Found in TagTemplate")]
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Slig Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_variant")
                box.prop(self, "has_weapontype")
                box.prop(self, "has_shieldtype")
                box.prop(self, "has_weaponscale")
                box.prop(self, "has_preloadclubanims")
                box.prop(self, "has_preloadgunanims")
                box.prop(self, "has_flipskinnormals")
                box.prop(self, "has_healthoverride")
                box.prop(self, "has_skinoverride")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_variant: layout.prop(self, "variant")
            if self.has_weapontype: layout.prop(self, "weapontype")
            if self.has_shieldtype: layout.prop(self, "shieldtype")
            if self.has_weaponscale: layout.prop(self, "weaponscale")
            if self.has_preloadclubanims: layout.prop(self, "preloadclubanims")
            if self.has_preloadgunanims: layout.prop(self, "preloadgunanims")
            if self.has_flipskinnormals: layout.prop(self, "flipskinnormals")
            if self.has_healthoverride: layout.prop(self, "healthoverride")
            if self.has_skinoverride: layout.prop(self, "skinoverride")

        def generate(self, obj):
            tag = f"<sliganimation componentguid='{self.componentguid}' "
            if self.has_preloadclubanims: tag += f"preloadclubanims='{self.preloadclubanims}' "
            if self.has_variant: tag += f"variant='{self.variant}' "
            if self.has_weapontype: tag += f"weapontype='{self.weapontype}' "
            if self.has_preloadgunanims: tag += f"preloadgunanims='{self.preloadgunanims}' "
            if self.has_shieldtype: tag += f"shieldtype='{self.shieldtype}' "
            if self.has_flipskinnormals: tag += f"flipskinnormals='{self.flipskinnormals}' "
            if self.has_healthoverride: tag += f"healthoverride='{self.healthoverride}' "
            if self.has_weaponscale: tag += f"weaponscale='{self.weaponscale}' "
            if self.has_skinoverride: tag += f"skinoverride='{self.skinoverride}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class Lever360Animation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_hidedecal: BoolProperty(name="Hide Decal", description="",default=True)

        def update_mesh(self, context):
            obj = context.object
            
            load_markers("lever_markers", [
                ("lever360", "markers/mechanics/lever360/lever360_base_bv/lever360_base_bv.obj")
            ])
            
            set_mesh(obj, "lever360")
            
            SelectObject(obj)
            
            set_modifier_node_group(obj, None)
            


        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        hidedecal: BoolProperty(
            name="Hide Decal", description="",
            default=False
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Lever 360 Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_hidedecal")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_hidedecal: layout.prop(self, "hidedecal")

        def generate(self, obj):
            tag = f"<lever360animation componentguid='{self.componentguid}' "
            if self.has_hidedecal: tag += f"hidedecal='{self.hidedecal}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class FootSwitchAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_breed: BoolProperty(name="Breed", description="",default=True)

        def update_mesh(self, context):
            obj = context.object
            
            
            load_markers("footswitch_markers", [
                ("footswitch_native", "markers/mechanics/footswitch/nnmet-00foo01_bv/nnmet-00foo01_bv.obj"),
                ("footswitch_civilized", "markers/mechanics/footswitch/ncmet-00foo01_bv/ncmet-00foo01_bv.obj")
            ])

            set_mesh(obj, f"footswitch_{self.breed}")
            
            SelectObject(obj)
            
            set_modifier_node_group(obj, None)
            
        def update_breed(self, context):
            obj = context.object
            update_mesh(context)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        breed: EnumProperty(
            name="Breed", description="",
            items=[
                ("native","Native","Found in TagTemplate"),
                ("civilized","Civilized","Generated from Real Data")
            ],
            update=update_breed
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Foot Switch Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_breed")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_breed: layout.prop(self, "breed")

        def generate(self, obj):
            tag = f"<footswitchanimation componentguid='{self.componentguid}' "
            if self.has_breed: tag += f"breed='{self.breed}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class FuzzleAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_flipskinnormals: BoolProperty(name="Flip Skin Normals", description="",default=False)
        has_skinoverride: BoolProperty(name="Skin Override", description="",default=False)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        
        def update_mesh(self, context):
            obj = context.object
            
            load_markers("fuzzle_markers",[
                ("fuzzle", "markers/characters/fuzzle/fuzzle_base_bv/fuzzle_base_bv.obj")
            ])
            
            obj.data = bpy.data.meshes["fuzzle"]
            
            set_modifier_node_group(obj, None)
            
            pass
        
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        flipskinnormals: BoolProperty(
            name="Flip Skin Normals", description="",
            default=False
        )

        skinoverride: EnumProperty(
            name="Skin Override", description="",
            items=[("UseDefault","Use Default","Found in TagTemplate")]
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Fuzzle Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_flipskinnormals")
                box.prop(self, "has_skinoverride")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_flipskinnormals: layout.prop(self, "flipskinnormals")
            if self.has_skinoverride: layout.prop(self, "skinoverride")

        def generate(self, obj):
            tag = f"<fuzzleanimation componentguid='{self.componentguid}' "
            if self.has_flipskinnormals: tag += f"flipskinnormals='{self.flipskinnormals}' "
            if self.has_skinoverride: tag += f"skinoverride='{self.skinoverride}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class VendingMachineAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_filename: BoolProperty(name="Filename", description="",default=True)

        def update_mesh(self, context):
            obj = context.object
            
            GR = bpy.context.scene.XinMO_Folder.gameroot
            print(f"{GR}/{self.filename[5:]}")
            if not os.path.exists(f"{GR}/{self.filename[5:].lower()}"): return
            
            fn = self.filename.replace('\\','/').split('/')[-1].split('.')[0]
            path = self.filename[5:-4].lower()
            print(f"{path}/{fn}")
            if not os.path.exists(f"{GR}/editor/markers/{path}/{fn}.obj"):
                # srcNIF, outFolder, gameroot
                outFolder = f"{GR}/editor/markers/{path}"
                CreateFolder(outFolder)
                LoadAndExportModel(
                        srcNIF=f"{GR}/{path}.nif", 
                        outFolder=outFolder,
                        gameroot=GR
                    )
            #./../Mechanics/VendingMachine/bounce_bv.nif
            load_markers("vendo_markers", [
                (fn, f"markers/{path}/{fn}.obj")
            ])
            
            set_mesh(obj, fn)
            SelectObject(obj)
            set_modifier_node_group(obj, None)

        def update_filepath(self, context):
            obj = context.object
            make_path_absolute(self, 'filename')    
            update_mesh(context)

        def update_vendo_builtin(self, context):
            obj = context.object
            match(self.vendo_builtin):
                case "bounce": self.filename = "./../Mechanics/VendingMachine/bounce_bv.nif"
                case "aquabounce": self.filename = "./../Mechanics/VendingMachine/aquabounce_vendo_bv.nif"
                case "energy": self.filename = "./../Mechanics/VendingMachine/energy_bv.nif"
                case "expresso": self.filename = "./../Mechanics/VendingMachine/expresso_bv.nif"
                case "healthup": self.filename = "./../Mechanics/VendingMachine/healthup_vendo_bv.nif"
                case "invisible": self.filename = "./../Mechanics/VendingMachine/invisible_bv.nif"
                case "klimb": self.filename = "./../Mechanics/VendingMachine/klimb_bv.nif"
                case "zap": self.filename = "./../Mechanics/VendingMachine/zapvendo_bv.nif"
                case "natbounce": self.filename = "./../Mechanics/VendingMachine/native_bounce_bv.nif"
                case "nataquabaounce": self.filename = "./../Mechanics/VendingMachine/native_aquabounce_bv.nif"
                case "natenergy": self.filename = "./../Mechanics/VendingMachine/native_energy_bv.nif"
                case "natsobe": self.filename = "./../Mechanics/VendingMachine/native_sobe_bv.nif"
                case "natexpresso": self.filename = "./../Mechanics/VendingMachine/native_expresso_bv.nif"
                case "nathealthup": self.filename = "./../Mechanics/VendingMachine/native_healthup_bv.nif"
                case "natzap": self.filename = "./../Mechanics/VendingMachine/native_zapvendo_bv.nif"
                case "blitz": self.filename = "./../Mechanics/VendingMachine/blitzpacker_bv.nif"
                case "saw": self.filename = "./../Mechanics/VendingMachine/saw_vendo_bv.nif"
                case "snuzi": self.filename = "./../Mechanics/VendingMachine/snuzi_vendo_bv.nif"
                case "lulu": self.filename = "./../Mechanics/VendingMachine/lulufund_bv.nif"

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)

        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        vendo_builtin: EnumProperty(
            name="Vendo Picker", description="This is a quick way of picking a vendo file. It will change the Filename property.",
            items=[
                ("bounce", "Bounce", "Mad hops in a can"),
                ("aquabounce", "Aqua Bounce", "Mad water hops in a can"),
                ("energy", "Energy", "cut from game, sobe related"),
                ("expresso", "Expresso", "MMmm tasty... why is everyone moving in slow motion"),
                ("healthup", "Health Up", "This cant be good for me but I feel great"),
                ("invisible", "Invisible", "Im a ghost"),
                ("klimb", "Klimb", "Walking on walls is no problem for me"),
                ("zap", "Zap", "Shocking"),
                ("natbounce", "Native Bounce", "Get mad hops, In style"),
                ("nataquabaounce", "Native Aqua Bounce", "Get mad water hops, In Style"),
                ("natenergy", "Native Energy", "cut from game, sobe related"),
                ("natsobe", "Native Sobe", "cut from game, sobe"),
                ("natexpresso", "Native Expresso", "MMmm tasty... why is everyone moving in slow motion, In Style?"),
                ("nathealthup", "Native Health Up", "This tastes great. Ok now this is silly... In Style"),
                ("natzap", "Native Zap", "Shocking... In Style"),
                ("blitz", "Blitz Packer", "Big gun for Big bros (sligs can use 'em too)"),
                ("saw", "Saw", "Get your slicey dicey tools here"),
                ("snuzi", "Snuzi", "Sleep darts. Yea... sleep... perminently"),
                ("lulu", "Lulu Fund", "The one and only, Donate your life savings today")
            ],
            update=update_vendo_builtin
        )
        filename: StringProperty(
            name="Filename", description="",
            default="./../Mechanics/VendingMachine/bounce_bv.nif",
            subtype="FILE_PATH", 
            update=update_filepath
        )
        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )

        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Vending Machine Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_filename")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")
            if self.has_filename: 
                layout.prop(self, "vendo_builtin")
                layout.prop(self, "filename")

        def generate(self, obj):
            tag = f"<vendingmachineanimation componentguid='{self.componentguid}' "
            if self.has_filename: tag += f"filename='{self.filename}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class BigBroAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_variant: BoolProperty(name="Variant", description="",default=True)
        has_weapontype: BoolProperty(name="Weapon Type", description="",default=True)
        has_shieldtype: BoolProperty(name="Shield Type", description="",default=True)
        has_flipskinnormals: BoolProperty(name="Flip Skin Normals", description="",default=False)
        has_healthoverride: BoolProperty(name="Health Override", description="",default=False)
        has_skinoverride: BoolProperty(name="Skin Override", description="",default=False)

        def update_variant(self, context):
            global allow_update
            if not allow_update: return
            update_mesh(context)
            
        def update_mesh(self, context):
            obj = context.object
            load_markers("bigbro_markers", [
                ("bigbro", "markers/characters/slig/bigbro_bv/bigbro_bv.obj"),
                ("bigbro_armor", "markers/characters/slig/bigbro_armor_bv/bigbro_armor_bv.obj"),
            ])
            SelectObject(obj)
            
            match(self.variant):
                case "basic": 
                    obj.data = bpy.data.meshes["bigbro"]
                case "armored":  
                    obj.data = bpy.data.meshes["bigbro_armor"]
            
            set_modifier_node_group(obj, None)
            set_modifier_node_group(obj, "SHADOWFIX", "BadShadowFix")
            set_modifier_socket(obj, "SHADOWFIX", "shadow", "shadow*NOSHADOW", True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        variant: EnumProperty(
            name="Variant", description="The kind of big bro",
            items=[
                ("basic","Basic","The standard big bro"),
                ("armored","Armored","A big bro with a shiny new upgrade.(His Armor)")
            ],
            update=update_variant
            
        )

        weapontype: EnumProperty(
            name="Weapon Type", description="",
            items=[
                ("UseDefault", "Use Default", "Found in TagTemplate"),
                ("NotAttached", "Not Attached", "Found in TagTemplate"),
                ("BrewGun","Brew Gun","Generated from Real Data"),
                ("SligClub","Slig Club","Generated from Real Data"),
                ("SligGun", "Slig Gun", "Found in TagTemplate"),
                ("DrugGun", "Drug Gun", "Found in TagTemplate"),
                ("CrossBow", "Cross Bow", "Found in TagTemplate"),
                ("ShockRod", "Shock Rod", "Found in TagTemplate"),
                ("Saw", "Saw", "Found in TagTemplate")
            ]
        )

        shieldtype: EnumProperty(
            name="Shield Type", description="",
            items=[
                ("UseDefault","Use Default","Found in TagTemplate"),
                ("NotAttached","Not Attached","Found in TagTemplate"),
                ("StandardShield","Standard Shield","Found in TagTemplate")
            ]
        )

        flipskinnormals: BoolProperty(
            name="Flip Skin Normals", description="",
            default=False
        )

        healthoverride: IntProperty(
            name="Health Override", description="",
            default=-1
        )

        skinoverride: EnumProperty(
            name="Skin Override", description="",
            items=[("UseDefault","Use Default","Found in TagTemplate")]
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Big Bro Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_variant")
                box.prop(self, "has_weapontype")
                box.prop(self, "has_shieldtype")
                box.prop(self, "has_flipskinnormals")
                box.prop(self, "has_healthoverride")
                box.prop(self, "has_skinoverride")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_variant: layout.prop(self, "variant")
            if self.has_weapontype: layout.prop(self, "weapontype")
            if self.has_shieldtype: layout.prop(self, "shieldtype")
            if self.has_flipskinnormals: layout.prop(self, "flipskinnormals")
            if self.has_healthoverride: layout.prop(self, "healthoverride")
            if self.has_skinoverride: layout.prop(self, "skinoverride")

        def generate(self, obj):
            tag = f"<bigbroanimation componentguid='{self.componentguid}' "
            if self.has_variant: tag += f"variant='{self.variant}' "
            if self.has_weapontype: tag += f"weapontype='{self.weapontype}' "
            if self.has_shieldtype: tag += f"shieldtype='{self.shieldtype}' "
            if self.has_flipskinnormals: tag += f"flipskinnormals='{self.flipskinnormals}' "
            if self.has_healthoverride: tag += f"healthoverride='{self.healthoverride}' "
            if self.has_skinoverride: tag += f"skinoverride='{self.skinoverride}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class NullAnimation(PropertyGroup):

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        def update_mesh(self, context):
            obj = context.object
            add_simple_marker("null_markers", "null_marker", bpy.ops.mesh.primitive_uv_sphere_add)
            if not bpy.data.objects["null_marker"].dimensions[0] >= 10:
                print("Fixing Null Marker")
                bpy.data.materials.new("null_marker_mat")
                mat = bpy.data.materials["null_marker_mat"]
                mat.use_nodes = True
                mat.use_backface_culling = True
                mat.surface_render_method = "BLENDED"
                mat.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.5
                bpy.data.objects["null_marker"].data.materials.append(mat)
                bpy.data.objects["null_marker"].dimensions = (10,10,10)
                apply_scale(bpy.data.objects["null_marker"])
                shade_smooth(bpy.data.objects["null_marker"])
                
            
            #if not obj.data.name == "null_marker":
            set_mesh(obj, "null_marker")
            SelectObject(obj)
            set_modifier_node_group(obj, None)
                
        
        
        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Null Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  

        def generate(self, obj):
            tag = f"<nullanimation componentguid='{self.componentguid}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class GlukkonAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_variant: BoolProperty(name="Variant", description="",default=True)
        has_flipskinnormals: BoolProperty(name="Flip Skin Normals", description="",default=False)
        has_healthoverride: BoolProperty(name="Health Override", description="",default=False)
        has_skinoverride: BoolProperty(name="Skin Override", description="",default=False)

        def update_variant(self, context):
            update_mesh(context)

        def update_mesh(self, context):
            obj = context.object
            
            load_markers("glukkon_markers", [
                ("pud", "markers/characters/glukkon/glukkon_pud_bv/glukkon_pud_bv.obj"),
                ("chump", "markers/characters/glukkon/glukkon_chump_bv/glukkon_chump_bv.obj"),
                ("wannabe", "markers/characters/glukkon/glukkon_wbe_bv/glukkon_wbe_bv.obj"),
                ("bigcheese", "markers/characters/glukkon/glukkon_bch_bv/glukkon_bch_bv.obj"),
                ("glokstar", "markers/characters/glukkon/glukkon_glk_bv/glukkon_glk_bv.obj")
            ])
            
            SelectObject(obj)
            
            set_mesh(obj, self.variant)
                        
            set_modifier_node_group(obj, None)
            
            

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        variant: EnumProperty(
            name="Variant", description="",
            items=[
                ("pud", "Pud", "The laziest glukk, he makes chump change, oh wait... not even that"),
                ("chump", "Chump", "Your average glukkon, makin' some small time moolah"),
                ("wannabe", "Wannabe", "He's tryin, but not quite there yet. He's probably spendin' it all"),
                ("bigcheese", "Big Cheese", "He's made it to the top. The spot where every glukk wants to be. Lots of moolah and no where to put it"),
                ("glokstar", "Glokstar", "He's better than the best, no one knows how he got all that cash")
            ],
            update=update_variant
        )

        flipskinnormals: BoolProperty(
            name="Flip Skin Normals", description="",
            default=False
        )

        healthoverride: IntProperty(
            name="Health Override", description="",
            default=-1
        )

        skinoverride: EnumProperty(
            name="Skin Override", description="",
            items=[
                ("UseDefault","Use Default","Found in TagTemplate")
            ]
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Glukkon Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_variant")
                box.prop(self, "has_flipskinnormals")
                box.prop(self, "has_healthoverride")
                box.prop(self, "has_skinoverride")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_variant: layout.prop(self, "variant")
            if self.has_flipskinnormals: layout.prop(self, "flipskinnormals")
            if self.has_healthoverride: layout.prop(self, "healthoverride")
            if self.has_skinoverride: layout.prop(self, "skinoverride")

        def generate(self, obj):
            tag = f"<glukkonanimation componentguid='{self.componentguid}' "
            if self.has_variant: tag += f"variant='{self.variant}' "
            if self.has_flipskinnormals: tag += f"flipskinnormals='{self.flipskinnormals}' "
            if self.has_healthoverride: tag += f"healthoverride='{self.healthoverride}' "
            if self.has_skinoverride: tag += f"skinoverride='{self.skinoverride}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class WheelchairAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_flipskinnormals: BoolProperty(name="Flip Skin Normals", description="",default=False)

        def update_mesh(self, context):
            obj = context.object
            
            load_markers("wheelchair_markers", [
                ("wheelchair", "markers/vehicles/wheelchair/wheelchair_base_bv/wheelchair_base_bv.obj")
            ])
            
            set_mesh(obj, "wheelchair")
            
            set_modifier_node_group(obj, None)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        flipskinnormals: BoolProperty(
            name="Flip Skin Normals", description="",
            default=False
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Wheelchair Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_flipskinnormals")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_flipskinnormals: layout.prop(self, "flipskinnormals")

        def generate(self, obj):
            tag = f"<wheelchairanimation componentguid='{self.componentguid}' "
            if self.has_flipskinnormals: tag += f"flipskinnormals='{self.flipskinnormals}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class ParamiteAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_flipskinnormals: BoolProperty(name="Flip Skin Normals", description="",default=False)
        has_skinoverride: BoolProperty(name="Skin Override", description="",default=False)

        def update_mesh(self, context):
            obj = context.object
            load_markers("paramite_markers",[
                ("paramite", "markers/characters/paramite/paramite_base_bv/paramite_base_bv.obj")
            ])
            
            set_modifier_node_group(obj, None)
            
            SelectObject(obj)
            
            obj.data = bpy.data.meshes[f"paramite"]

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        flipskinnormals: BoolProperty(
            name="Flip Skin Normals", description="",
            default=False
        )

        skinoverride: EnumProperty(
            name="Skin Override", description="",
            items=[
                ("UseDefault","Use Default","Found in TagTemplate")
            ]
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Paramite Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_flipskinnormals")
                box.prop(self, "has_skinoverride")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_flipskinnormals: layout.prop(self, "flipskinnormals")
            if self.has_skinoverride: layout.prop(self, "skinoverride")

        def generate(self, obj):
            tag = f"<paramiteanimation componentguid='{self.componentguid}' "
            if self.has_flipskinnormals: tag += f"flipskinnormals='{self.flipskinnormals}' "
            if self.has_skinoverride: tag += f"skinoverride='{self.skinoverride}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class ScrabAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_flipskinnormals: BoolProperty(name="Flip Skin Normals", description="",default=False)
        has_skinoverride: BoolProperty(name="Skin Override", description="",default=False)

        def update_mesh(self, context):
            obj = context.object
            
            load_markers("scrab_markers", [
                ("scrab", "markers/characters/scrab/scrab_base_bv/scrab_base_bv.obj")
            ])
            
            SelectObject(obj)
            
            obj.data = bpy.data.meshes["scrab"]

            set_modifier_node_group(obj, None)
            set_modifier_node_group(obj, "SHADOWFIX", "BadShadowFix")
            set_modifier_socket(obj, "SHADOWFIX", "shadow", "shadow*NOSHADOW", True)


        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        flipskinnormals: BoolProperty(
            name="Flip Skin Normals", description="",
            default=False
        )

        skinoverride: EnumProperty(
            name="Skin Override", description="",
            items=[
                ("UseDefault","Use Default","Found in TagTemplate")
            ]
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Scrab Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_flipskinnormals")
                box.prop(self, "has_skinoverride")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_flipskinnormals: layout.prop(self, "flipskinnormals")
            if self.has_skinoverride: layout.prop(self, "skinoverride")

        def generate(self, obj):
            tag = f"<scrabanimation componentguid='{self.componentguid}' "
            if self.has_flipskinnormals: tag += f"flipskinnormals='{self.flipskinnormals}' "
            if self.has_skinoverride: tag += f"skinoverride='{self.skinoverride}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class GenericParticlesAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_filename: BoolProperty(name="Filename", description="",default=True)
        has_particletype: BoolProperty(name="Particle Type", description="",default=True)
        has_looping: BoolProperty(name="Looping", description="",default=False)
        has_canclimb: BoolProperty(name="Can Climb", description="",default=False)

        def update_filepath(self, context):
            make_path_absolute(self, 'filename')


        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        filename: StringProperty(
            name="Filename", description="",
            default="./../Effects/genericparticles.nif",
            subtype="FILE_PATH", 
            update=update_filepath
        )

        particletype: EnumProperty(
            name="Particle Type", description="",
            items=[
                ("kSmoke","Smoke","Found in TagTemplate"),
                ("kTreeFire","Tree Fire","Found in TagTemplate"),
                ("kAreaGroundFire","Area Ground Fire","Found in TagTemplate"),
                ("kSpray","Spray","Found in TagTemplate"),
                ("kRain","Rain","Found in TagTemplate"),
                ("kGasJets","Gas Jets","Found in TagTemplate"),
                ("kSawdust","Sawdust","Found in TagTemplate"),
                ("kDriftingLeaves","Drifting Leaves","Found in TagTemplate"),
                ("kFromFile","From File","Generated from Real Data")
            ]
        )

        looping: BoolProperty(
            name="Looping", description="",
            default=True
        )

        canclimb: BoolProperty(
            name="Can Climb", description="",
            default=False
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Generic Particles Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_filename")
                box.prop(self, "has_particletype")
                box.prop(self, "has_looping")
                box.prop(self, "has_canclimb")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_filename: layout.prop(self, "filename")
            if self.has_particletype: layout.prop(self, "particletype")
            if self.has_looping: layout.prop(self, "looping")
            if self.has_canclimb: layout.prop(self, "canclimb")

        def generate(self, obj):
            tag = f"<genericparticlesanimation componentguid='{self.componentguid}' "
            if self.has_filename: tag += f"filename='{self.filename}' "
            if self.has_particletype: tag += f"particletype='{self.particletype}' "
            if self.has_looping: tag += f"looping='{self.looping}' "
            if self.has_canclimb: tag += f"canclimb='{self.canclimb}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class MeepAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_golden: BoolProperty(name="Golden", description="",default=True)
        has_flipskinnormals: BoolProperty(name="Flip Skin Normals", description="",default=False)
        has_skinoverride: BoolProperty(name="Skin Override", description="",default=False)

        def update_golden(self, context):
            global allow_update
            if not allow_update: return
            update_mesh(context)

        def update_mesh(self, context):
            obj = context.object
            load_markers("meep_markers",[
                ("meep", "markers/characters/meep/meep_base_bv/meep_base_bv.obj"),
                ("meep_gold", "markers/characters/meep/meep_golden_base_bv/meep_golden_base_bv.obj"),               
            ])
            
            SelectObject(obj)
            
            if self.golden: 
                obj.data = bpy.data.meshes[f"meep_gold"]
            else: 
                obj.data = bpy.data.meshes[f"meep"]

            set_modifier_node_group(obj, None)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        golden: BoolProperty(
            name="Golden", description="",
            default=False,
            update=update_golden
        )

        flipskinnormals: BoolProperty(
            name="Flip Skin Normals", description="",
            default=False
        )

        skinoverride: EnumProperty(
            name="Skin Override", description="",
            items=[
                ("UseDefault","UseDefault","Generated default with script")
            ],
            default="UseDefault"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Meep Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_golden")
                box.prop(self, "has_flipskinnormals")
                box.prop(self, "has_skinoverride")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_golden: layout.prop(self, "golden")
            if self.has_flipskinnormals: layout.prop(self, "flipskinnormals")
            if self.has_skinoverride: layout.prop(self, "skinoverride")

        def generate(self, obj):
            tag = f"<meepanimation componentguid='{self.componentguid}' "
            if self.has_golden: tag += f"golden='{self.golden}' "
            if self.has_flipskinnormals: tag += f"flipskinnormals='{self.flipskinnormals}' "
            if self.has_skinoverride: tag += f"skinoverride='{self.skinoverride}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class InternAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_light: BoolProperty(name="Light", description="",default=True)
        has_preloadgunanims: BoolProperty(name="Preload Gun Animations", description="",default=True)
        has_preloadclubanims: BoolProperty(name="Preload Club Animations", description="",default=False)
        has_variant: BoolProperty(name="Variant", description="",default=True)
        has_weapontype: BoolProperty(name="Weapon Type", description="",default=True)
        has_flipskinnormals: BoolProperty(name="Flip Skin Normals", description="",default=False)
        has_healthoverride: BoolProperty(name="Health Override", description="",default=False)
        
        def update_variant(self, context):
            update_mesh(context)

        def update_mesh(self, context):
            obj = context.object
            
            load_markers("intern_markers",[
                ("worker", "markers/characters/intern/intern_worker_bv/intern_worker_bv.obj"),
                ("armored", "markers/characters/intern/intern_armor_bv/intern_armor_bv.obj"),
                ("shooter", "markers/characters/intern/intern_shooter_bv/intern_shooter_bv.obj"),
                ("shocker", "markers/characters/intern/intern_shocker_bv/intern_shocker_bv.obj")
            ])

            SelectObject(obj)
            
            set_mesh(obj, self.variant)
            
            set_modifier_group_node(obj, None)


        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        light: BoolProperty(
            name="Light", description="",
            default=False
        )

        preloadgunanims: BoolProperty(
            name="Preload Gun Animations", description="",
            default=False
        )

        preloadclubanims: BoolProperty(
            name="Preload Club Animations", description="",
            default=False
        )

        variant: EnumProperty(
            name="Variant", description="",
            items=[
                ("worker","worker","He works and works.., also this is the HD variant"),
                ("armored","Armored","He's a guard, and he likes to guard, and sometimes shoot things"),
                ("shooter","Shooter","Mind that syring gun he has, or you'll end up a test subject for the vykkers"),
                ("shocker","Shocker","Not implimented fully, at least the shock baton isnt anyway")
            ],
            default="worker",
            update=update_variant
        )

        weapontype: EnumProperty(
            name="Weapon Type", description="",
            items=[
                ("UseDefault","UseDefault","Generated default with script"),
                ("NotAttached","NotAttached","Found in TagTemplate"),
                ("DrugGun","DrugGun","Generated from Real Data"),
                ("SligGun","SligGun","Found in TagTemplate"),
                ("BrewGun","BrewGun","Found in TagTemplate"),
                ("SligClub","SligClub","Found in TagTemplate"),
                ("ShockRod","ShockRod","Found in TagTemplate"),
                ("Saw","Saw","Found in TagTemplate")
            ],
            default="UseDefault"
        )

        flipskinnormals: BoolProperty(
            name="Flip Skin Normals", description="",
            default=False
        )

        healthoverride: IntProperty(
            name="Health Override", description="",
            default=-1
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Intern Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_variant")
                box.prop(self, "has_weapontype")
                box.prop(self, "has_light")
                box.prop(self, "has_preloadgunanims")
                box.prop(self, "has_preloadclubanims")
                box.prop(self, "has_flipskinnormals")
                box.prop(self, "has_healthoverride")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_variant: layout.prop(self, "variant")
            if self.has_weapontype: layout.prop(self, "weapontype")
            if self.has_light: layout.prop(self, "light")
            if self.has_preloadgunanims: layout.prop(self, "preloadgunanims")
            if self.has_preloadclubanims: layout.prop(self, "preloadclubanims")
            if self.has_flipskinnormals: layout.prop(self, "flipskinnormals")
            if self.has_healthoverride: layout.prop(self, "healthoverride")

        def generate(self, obj):
            tag = f"<internanimation componentguid='{self.componentguid}' "
            if self.has_light: tag += f"light='{self.light}' "
            if self.has_preloadgunanims: tag += f"preloadgunanims='{self.preloadgunanims}' "
            if self.has_preloadclubanims: tag += f"preloadclubanims='{self.preloadclubanims}' "
            if self.has_variant: tag += f"variant='{self.variant}' "
            if self.has_weapontype: tag += f"weapontype='{self.weapontype}' "
            if self.has_flipskinnormals: tag += f"flipskinnormals='{self.flipskinnormals}' "
            if self.has_healthoverride: tag += f"healthoverride='{self.healthoverride}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class SlogAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_flipskinnormals: BoolProperty(name="Flip Skin Normals", description="",default=False)
        has_skinoverride: BoolProperty(name="Skin Override", description="",default=False)

        def update_mesh(self, context):
            obj = context.object
            
            load_markers("slog_markers",[
                ("slog", "markers/characters/slog/slog_base_bv/slog_base_bv.obj")
            ])

            SelectObject(obj)
            
            obj.data = bpy.data.meshes["slog"]
            
            set_modifier_group_node(obj, None)


        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        flipskinnormals: BoolProperty(
            name="Flip Skin Normals", description="",
            default=False
        )

        skinoverride: EnumProperty(
            name="Skin Override", description="",
            items=[
                ("UseDefault","UseDefault","Generated default with script")
            ],
            default="UseDefault"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Slog Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_flipskinnormals")
                box.prop(self, "has_skinoverride")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_flipskinnormals: layout.prop(self, "flipskinnormals")
            if self.has_skinoverride: layout.prop(self, "skinoverride")

        def generate(self, obj):
            tag = f"<sloganimation componentguid='{self.componentguid}' "
            if self.has_flipskinnormals: tag += f"flipskinnormals='{self.flipskinnormals}' "
            if self.has_skinoverride: tag += f"skinoverride='{self.skinoverride}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class VykkerAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_variant: BoolProperty(name="Variant", description="",default=True)
        has_weapontype: BoolProperty(name="Weapon Type", description="",default=True)
        has_shieldtype: BoolProperty(name="Shield Type", description="",default=False)
        has_preloadgunanims: BoolProperty(name="Preload Gun Animations", description="",default=True)
        has_preloadclubanims: BoolProperty(name="Preload Club Animations", description="",default=False)
        has_flipskinnormals: BoolProperty(name="Flip Skin Normals", description="",default=False)
        has_healthoverride: BoolProperty(name="Health Override", description="",default=False)
        has_skinoverride: BoolProperty(name="Skin Override", description="",default=False)

        def update_variant(self, context):
            update_mesh(context)

        def update_mesh(self, context):
            obj = context.object
            
            load_markers("vykker_markers",[
                ("vykker_worker", "markers/characters/vykker/vykker_base_bv/vykker_base_bv.obj"),
                ("vykker_armored", "markers/characters/vykker/vykker_armor_bv/vykker_armor_bv.obj")
            ])

            SelectObject(obj)
            
            suffex = "worker" if self.variant in ["sawbones", "surgeon"] else self.variant
            set_mesh(obj, f"vykker_{suffex}")
            
            set_modifier_group_node(obj, None)


        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        variant: EnumProperty(
            name="Variant", description="",
            items=[
                ("worker","worker","A vykker, im sure he wont hesitate to extract your organs for a good laugh"),
                ("armored","Armored","This vykker was prepared for some nuisances in the lab"),
                ("sawbones","Sawbones","Although this was found in the real data there is no model for it. (will use worker)"),
                ("surgeon","Surgeon","Although this was found in the tag template there is no model for it. (will use worker)")
            ],
            default="worker",
            update=update_variant
        )

        weapontype: EnumProperty(
            name="Weapon Type", description="",
            items=[
                ("UseDefault","UseDefault","Generated default with script"),
                ("NotAttached","NotAttached","Generated from Real Data"),
                ("Saw","Saw","Generated from Real Data"),
                ("SligGun","Slig Gun","Found in TagTemplate"),
                ("BrewGun","Brew Gun","Found in TagTemplate"),
                ("DrugGun","Drug Gun","Found in TagTemplate"),
                ("CrossBow","Cross Bow","Found in TagTemplate"),
                ("SligClub","Slig Club","Found in TagTemplate"),
                ("ShockRod","Shock Rod","Found in TagTemplate")
            ],
            default="UseDefault"
        )

        shieldtype: EnumProperty(
            name="Shield Type", description="",
            items=[
                ("UseDefault","UseDefault","Generated default with script"),
                ("NotAttached","Not Attached","Found in TagTemplate"),
                ("StandardShield","Standard Shield","Found in TagTemplate")
            ],
            default="UseDefault"
        )

        preloadgunanims: BoolProperty(
            name="Preload Gun Animations", description="",
            default=False
        )

        preloadclubanims: BoolProperty(
            name="Preload Club Animations", description="",
            default=False
        )

        flipskinnormals: BoolProperty(
            name="Flip Skin Normals", description="",
            default=False
        )

        healthoverride: IntProperty(
            name="Health Override", description="",
            default=-1
        )

        skinoverride: EnumProperty(
            name="Skin Override", description="",
            items=[
                ("UseDefault","UseDefault","Generated default with script")
            ],
            default="UseDefault"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Vykker Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_variant")
                box.prop(self, "has_weapontype")
                box.prop(self, "has_shieldtype")
                box.prop(self, "has_preloadgunanims")
                box.prop(self, "has_preloadclubanims")
                box.prop(self, "has_flipskinnormals")
                box.prop(self, "has_healthoverride")
                box.prop(self, "has_skinoverride")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_variant: layout.prop(self, "variant")
            if self.has_weapontype: layout.prop(self, "weapontype")
            if self.has_shieldtype: layout.prop(self, "shieldtype")
            if self.has_preloadgunanims: layout.prop(self, "preloadgunanims")
            if self.has_preloadclubanims: layout.prop(self, "preloadclubanims")
            if self.has_flipskinnormals: layout.prop(self, "flipskinnormals")
            if self.has_healthoverride: layout.prop(self, "healthoverride")
            if self.has_skinoverride: layout.prop(self, "skinoverride")

        def generate(self, obj):
            tag = f"<vykkeranimation componentguid='{self.componentguid}' "
            if self.has_variant: tag += f"variant='{self.variant}' "
            if self.has_weapontype: tag += f"weapontype='{self.weapontype}' "
            if self.has_shieldtype: tag += f"shieldtype='{self.shieldtype}' "
            if self.has_preloadgunanims: tag += f"preloadgunanims='{self.preloadgunanims}' "
            if self.has_preloadclubanims: tag += f"preloadclubanims='{self.preloadclubanims}' "
            if self.has_flipskinnormals: tag += f"flipskinnormals='{self.flipskinnormals}' "
            if self.has_healthoverride: tag += f"healthoverride='{self.healthoverride}' "
            if self.has_skinoverride: tag += f"skinoverride='{self.skinoverride}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class RecyclerAnimation(PropertyGroup):

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        def update_mesh(self, context):
            obj = context.object
            load_markers("recycler_markers", [
                ("recycler", "markers/mechanics/recycler/recycler_base_bv/recycler_base_bv.obj")
            ])
            set_mesh(obj, "recycler")
            set_modifier_node_group(obj, None)
        
        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Recycler Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  

        def generate(self, obj):
            tag = f"<recycleranimation componentguid='{self.componentguid}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class CandyStriperAnimation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_weapontype: BoolProperty(name="Weapon Type", description="",default=False)
        has_weaponscale: BoolProperty(name="Weapon Scale", description="",default=False)
        has_flipskinnormals: BoolProperty(name="Flip Skin Normals", description="",default=False)
        has_skinoverride: BoolProperty(name="Skin Override", description="",default=False)

        def update_mesh(self, context):
            obj = context.object
            
            load_markers("candystriper_markers",[
                ("candystriper", "markers/characters/striper/striper_base_bv/striper_base_bv.obj")
            ])

            SelectObject(obj)
            
            set_mesh(obj, "candystriper")
            
            set_modifier_group_node(obj, None)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        flipskinnormals: BoolProperty(
            name="Flip Skin Normals", description="",
            default=False
        )

        weaponscale: FloatProperty(
            name="Weapon Scale", description="",
            default=1
        )

        weapontype: EnumProperty(
            name="Weapon Type", description="",
            items=[
                ("UseDefault","UseDefault","Generated default with script"),
                ("NotAttached","NotAttached","Found in TagTemplate"),
                ("MuzzleFlash","Muzzle Flash","Found in TagTemplate")
            ],
            default="UseDefault"
        )

        skinoverride: EnumProperty(
            name="Skin Override", description="",
            items=[
                ("UseDefault","UseDefault","Generated default with script")
            ],
            default="UseDefault"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Candy Striper Animation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_weapontype")
                box.prop(self, "has_weaponscale")
                box.prop(self, "has_flipskinnormals")
                box.prop(self, "has_skinoverride")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_weapontype: layout.prop(self, "weapontype")
            if self.has_weaponscale: layout.prop(self, "weaponscale")
            if self.has_flipskinnormals: layout.prop(self, "flipskinnormals")
            if self.has_skinoverride: layout.prop(self, "skinoverride")

        def generate(self, obj):
            tag = f"<candystriperanimation componentguid='{self.componentguid}' "
            if self.has_flipskinnormals: tag += f"flipskinnormals='{self.flipskinnormals}' "
            if self.has_weaponscale: tag += f"weaponscale='{self.weaponscale}' "
            if self.has_weapontype: tag += f"weapontype='{self.weapontype}' "
            if self.has_skinoverride: tag += f"skinoverride='{self.skinoverride}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class Behavior(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_script: BoolProperty(name="Script", description="",default=True)
        has_variables: BoolProperty(name="Variables", description="",default=True)
        has_behavior: BoolProperty(name="Behavior", description="",default=True)
        has_body: BoolProperty(name="Body", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        script: StringProperty(
            name="Script", description="",
            default="included"
        )

        variables: StringProperty(
            name="Variables", description="",
            default=""
        )

        behavior: EnumProperty(
            name="Behavior", description="",
            items=[
                ("kRunScript","Run Script","Generated from Real Data"),
                ("kIdle","Idle","Generated from Real Data")
            ],
            default="kRunScript"
        )

        body: StringProperty(
            name="Body", description="",
            default=""
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Behavior")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_script")
                box.prop(self, "has_variables")
                box.prop(self, "has_behavior")
                box.prop(self, "has_body")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_script: layout.prop(self, "script")
            if self.has_variables: layout.prop(self, "variables")
            if self.has_behavior: layout.prop(self, "behavior")
            if self.has_body: layout.prop(self, "body")

        def generate(self, obj):
            tag = f"<behavior componentguid='{self.componentguid}' "
            if self.has_script: tag += f"script='{self.script}' "
            if self.has_variables: tag += f"variables='{self.variables}' "
            if self.has_behavior: tag += f"behavior='{self.behavior}' "
            if self.has_body: tag += f"body='{self.body}' "
            tag += "/>"
            return tag
    class Job(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_script: BoolProperty(name="Script", description="",default=True)
        has_variables: BoolProperty(name="Variables", description="",default=False)
        has_body: BoolProperty(name="Body", description="",default=True)
        has_timeout: BoolProperty(name="Time Out", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        script: StringProperty(
            name="Script", description="",
            default="included"
        )

        variables: StringProperty(
            name="Variables", description="",
            default=""
        )

        body: StringProperty(
            name="Body", description="",
            default=""
        )

        timeout: IntProperty(
            name="Time Out", description="",
            default=10
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Job")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_script")
                box.prop(self, "has_variables")
                box.prop(self, "has_body")
                box.prop(self, "has_timeout")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_script: layout.prop(self, "script")
            if self.has_variables: layout.prop(self, "variables")
            if self.has_body: layout.prop(self, "body")
            if self.has_timeout: layout.prop(self, "timeout")

        def generate(self, obj):
            tag = f"<job componentguid='{self.componentguid}' "
            if self.has_script: tag += f"script='{self.script}' "
            if self.has_variables: tag += f"variables='{self.variables}' "
            if self.has_body: tag += f"body='{self.body}' "
            if self.has_timeout: tag += f"timeout='{self.timeout}' "
            tag += "/>"
            return tag
    class Doves(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_beginstate: BoolProperty(name="Begin State", description="",default=True)
        has_model: BoolProperty(name="Model", description="",default=False)
        has_numdoves: BoolProperty(name="Number Doves", description="",default=True)
        has_healthheight: BoolProperty(name="Health Height", description="",default=True)
        has_healthseconds: BoolProperty(name="Health Seconds", description="",default=True)
        has_radius: BoolProperty(name="Radius", description="",default=False)
        has_minradius: BoolProperty(name="Minimum Radius", description="",default=False)
        has_maxradius: BoolProperty(name="Maximum Radius", description="",default=False)
        has_angularvel: BoolProperty(name="Angular Velocity", description="",default=False)
        has_zangularvel: BoolProperty(name="Z Angular Velocity", description="",default=False)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        numdoves: IntProperty(
            name="Number Doves", description="",
            default=10
        )

        radius: FloatProperty(
            name="Radius", description="",
            default=15
        )

        minradius: FloatProperty(
            name="Minimum Radius", description="",
            default=4
        )

        maxradius: FloatProperty(
            name="Maximum Radius", description="",
            default=15
        )

        angularvel: FloatProperty(
            name="Angular Velocity", description="",
            default=3
        )

        zangularvel: FloatProperty(
            name="Z Angular Velocity", description="",
            default=1
        )

        healthseconds: FloatProperty(
            name="Health Seconds", description="",
            default=3
        )

        healthheight: FloatProperty(
            name="Health Height", description="",
            default=18
        )

        beginstate: EnumProperty(
            name="Begin State", description="",
            items=[
                ("kOffScreen","Off Screen","Generated default with script"),
                ("kCircling","Circling","Found in TagTemplate")
            ],
            default="kOffScreen"
        )

        model: EnumProperty(
            name="Model", description="",
            items=[
                ("dove","Dove","Generated default with script"),
                ("fly","Fly","Found in TagTemplate")
            ],
            default="dove"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Doves")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_model")
                box.prop(self, "has_beginstate")
                box.prop(self, "has_numdoves")
                box.prop(self, "has_healthheight")
                box.prop(self, "has_healthseconds")
                box.prop(self, "has_radius")
                box.prop(self, "has_minradius")
                box.prop(self, "has_maxradius")
                box.prop(self, "has_angularvel")
                box.prop(self, "has_zangularvel")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_model: layout.prop(self, "model")
            if self.has_beginstate: layout.prop(self, "beginstate")
            if self.has_numdoves: layout.prop(self, "numdoves")
            if self.has_healthheight: layout.prop(self, "healthheight")
            if self.has_healthseconds: layout.prop(self, "healthseconds")
            if self.has_radius: layout.prop(self, "radius")
            if self.has_minradius: layout.prop(self, "minradius")
            if self.has_maxradius: layout.prop(self, "maxradius")
            if self.has_angularvel: layout.prop(self, "angularvel")
            if self.has_zangularvel: layout.prop(self, "zangularvel")

        def generate(self, obj):
            tag = f"<doves componentguid='{self.componentguid}' "
            if self.has_numdoves: tag += f"numdoves='{self.numdoves}' "
            if self.has_radius: tag += f"radius='{self.radius}' "
            if self.has_minradius: tag += f"minradius='{self.minradius}' "
            if self.has_maxradius: tag += f"maxradius='{self.maxradius}' "
            if self.has_angularvel: tag += f"angularvel='{self.angularvel}' "
            if self.has_zangularvel: tag += f"zangularvel='{self.zangularvel}' "
            if self.has_healthseconds: tag += f"healthseconds='{self.healthseconds}' "
            if self.has_healthheight: tag += f"healthheight='{self.healthheight}' "
            if self.has_beginstate: tag += f"beginstate='{self.beginstate}' "
            if self.has_model: tag += f"model='{self.model}' "
            tag += "/>"
            return tag
    class ZapFx(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_damage: BoolProperty(name="Damage", description="",default=True)
        has_lethal: BoolProperty(name="Lethal", description="",default=True)
        has_effectseconds: BoolProperty(name="Effect Seconds", description="",default=True)
        has_effectoffset: BoolProperty(name="Effect Offset", description="",default=False)
        has_wiggle: BoolProperty(name="Wiggle", description="",default=True)
        has_wiggletimescale: BoolProperty(name="Wiggle Time Scale", description="",default=True)
        has_sourcezigzag: BoolProperty(name="Source Zigzag", description="",default=True)
        has_destinationzigzag: BoolProperty(name="Destination Zigzag", description="",default=True)
        has_colora: BoolProperty(name="Color Alpha", description="",default=True)
        has_lightcolor: BoolProperty(name="Light Color", description="",default=True)
        has_segments: BoolProperty(name="Segments", description="",default=True)
        has_addtohud: BoolProperty(name="Add To Hud", description="",default=True)
        has_width: BoolProperty(name="Width", description="",default=True)
        has_amplitude: BoolProperty(name="Amplitude", description="",default=True)
        has_usedynamiclight: BoolProperty(name="Use Dynamic Light", description="",default=True)
        has_knockbacktarget: BoolProperty(name="Knockback Target", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        segments: IntProperty(
            name="Segments", description="",
            default=25
        )

        width: FloatProperty(
            name="Width", description="",
            default=3
        )

        amplitude: FloatProperty(
            name="Amplitude", description="",
            default=0.4
        )

        wiggle: FloatProperty(
            name="Wiggle", description="",
            default=0.1
        )

        wiggletimescale: IntProperty(
            name="Wiggle Time Scale", description="",
            default=8
        )

        sourcezigzag: FloatProperty(
            name="Source Zigzag", description="",
            default=0.12
        )

        destinationzigzag: FloatProperty(
            name="Destination Zigzag", description="",
            default=0.02
        )

        colora: FloatVectorProperty(
            name="Color Alpha", description="",
            subtype="COLOR",
            min=0, max=1,
            size=4,
            default=(0.3,0.3,1.0,0.8)
        )

        effectseconds: FloatProperty(
            name="Effect Seconds", description="",
            default=1
        )

        damage: FloatProperty(
            name="Damage", description="",
            default=0
        )

        effectoffset: FloatVectorProperty(
            name="Effect Offset", description="",
            subtype="XYZ",
            default=(0.0,0.0,0.0)
        )

        usedynamiclight: BoolProperty(
            name="Use Dynamic Light", description="",
            default=True
        )

        lightcolor: FloatVectorProperty(
            name="Light Color", description="",
            subtype="COLOR",
            min=0, max=1,
            default=(0.03921569,0.03921569,0.1176471)
        )

        knockbacktarget: BoolProperty(
            name="Knockback Target", description="",
            default=False
        )

        addtohud: BoolProperty(
            name="Add To Hud", description="",
            default=False
        )

        lethal: BoolProperty(
            name="Lethal", description="",
            default=True
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Zap Fx")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_damage")
                box.prop(self, "has_lethal")
                box.prop(self, "has_effectseconds")
                box.prop(self, "has_effectoffset")
                box.prop(self, "has_wiggle")
                box.prop(self, "has_wiggletimescale")
                box.prop(self, "has_sourcezigzag")
                box.prop(self, "has_destinationzigzag")
                box.prop(self, "has_colora")
                box.prop(self, "has_lightcolor")
                box.prop(self, "has_segments")
                box.prop(self, "has_addtohud")
                box.prop(self, "has_width")
                box.prop(self, "has_amplitude")
                box.prop(self, "has_usedynamiclight")
                box.prop(self, "has_knockbacktarget")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_damage: layout.prop(self, "damage")
            if self.has_lethal: layout.prop(self, "lethal")
            if self.has_effectseconds: layout.prop(self, "effectseconds")
            if self.has_effectoffset: layout.prop(self, "effectoffset")
            if self.has_wiggle: layout.prop(self, "wiggle")
            if self.has_wiggletimescale: layout.prop(self, "wiggletimescale")
            if self.has_sourcezigzag: layout.prop(self, "sourcezigzag")
            if self.has_destinationzigzag: layout.prop(self, "destinationzigzag")
            if self.has_colora: layout.prop(self, "colora")
            if self.has_lightcolor: layout.prop(self, "lightcolor")
            if self.has_segments: layout.prop(self, "segments")
            if self.has_addtohud: layout.prop(self, "addtohud")
            if self.has_width: layout.prop(self, "width")
            if self.has_amplitude: layout.prop(self, "amplitude")
            if self.has_usedynamiclight: layout.prop(self, "usedynamiclight")
            if self.has_knockbacktarget: layout.prop(self, "knockbacktarget")

        def generate(self, obj):
            tag = f"<zapfx componentguid='{self.componentguid}' "
            if self.has_segments: tag += f"segments='{self.segments}' "
            if self.has_width: tag += f"width='{self.width}' "
            if self.has_amplitude: tag += f"amplitude='{self.amplitude}' "
            if self.has_wiggle: tag += f"wiggle='{self.wiggle}' "
            if self.has_wiggletimescale: tag += f"wiggletimescale='{self.wiggletimescale}' "
            if self.has_sourcezigzag: tag += f"sourcezigzag='{self.sourcezigzag}' "
            if self.has_destinationzigzag: tag += f"destinationzigzag='{self.destinationzigzag}' "
            if self.has_colora: tag += f"colora='{self.colora[0]},{self.colora[1]},{self.colora[2]},{self.colora[3]}' "
            if self.has_effectseconds: tag += f"effectseconds='{self.effectseconds}' "
            if self.has_damage: tag += f"damage='{self.damage}' "
            if self.has_effectoffset: tag += f"effectoffset='{self.effectoffset[0]},{self.effectoffset[1]},{self.effectoffset[2]}' "
            if self.has_usedynamiclight: tag += f"usedynamiclight='{self.usedynamiclight}' "
            if self.has_lightcolor: tag += f"lightcolor='{self.lightcolor[0]*255},{self.lightcolor[1]*255},{self.lightcolor[2]*255}' "
            if self.has_knockbacktarget: tag += f"knockbacktarget='{self.knockbacktarget}' "
            if self.has_addtohud: tag += f"addtohud='{self.addtohud}' "
            if self.has_lethal: tag += f"lethal='{self.lethal}' "
            tag += "/>"
            return tag
    class AssetLock(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_isready: BoolProperty(name="Is Ready", description="",default=False)
        has_partialpayment: BoolProperty(name="Partial Payment", description="",default=True)
        has_assetamount: BoolProperty(name="Asset Amount", description="",default=True)
        has_activation: BoolProperty(name="Activation", description="",default=True)
        has_assettype: BoolProperty(name="Asset Type", description="",default=True)
        has_greetmsg: BoolProperty(name="Greet Message", description="",default=True)
        has_notreadymsg: BoolProperty(name="Not Ready Message", description="",default=True)
        has_lowassetmsg: BoolProperty(name="Low Asset Message", description="",default=True)
        has_script: BoolProperty(name="Script", description="",default=True)
        has_buttonradius: BoolProperty(name="Button Radius", description="",default=False)
        has_chantradius: BoolProperty(name="Chant Radius", description="",default=False)
        has_linkcomponentguid: BoolProperty(name="Link Component Guid", description="",default=True)
        has_multidisplayguid: BoolProperty(name="Multi Display Guid", description="",default=True)
        has_errdisplayguid: BoolProperty(name="Display Guid", description="",default=False)
        has_errordelay: BoolProperty(name="Error Delay", description="",default=False)
        has_particlevalue: BoolProperty(name="Particle Value", description="",default=True)
        has_particleoffset: BoolProperty(name="Particle Offset", description="",default=False)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        buttonradius: FloatProperty(
            name="Button Radius", description="",
            default=40
        )

        isready: BoolProperty(
            name="Is Ready", description="",
            default=True
        )

        assetamount: IntProperty(
            name="Asset Amount", description="",
            default=10
        )

        linkcomponentguid: IntProperty(
            name="Link Component Guid", description="",
            default=0
        )

        activation: EnumProperty(
            name="Activation", description="",
            items=[
                ("chant","Chant","Generated default with script"),
                ("button","Button","Generated from Real Data"),
                ("link","Link","Found in TagTemplate")
            ],
            default="chant"
        )

        script: StringProperty(
            name="Script", description="",
            default=""
        )

        assettype: EnumProperty(
            name="Asset Type", description="",
            items=[
                ("spooce","spooce","Generated default with script"),
                ("moolah","Moolah","Generated from Real Data")
            ],
            default="spooce"
        )

        greetmsg: StringProperty(
            name="Greet Message", description="",
            default="@@tASSET_1"
        )

        notreadymsg: StringProperty(
            name="Not Ready Message", description="",
            default="@@tASSET_2"
        )

        lowassetmsg: StringProperty(
            name="Low Asset Message", description="",
            default="@@tASSET_3"
        )

        errordelay: FloatProperty(
            name="Error Delay", description="",
            default=5
        )

        multidisplayguid: PointerProperty(
            name="Multi Display Guid", description="",
            type=bpy.types.Object,
            poll=poll_actors
        )

        partialpayment: BoolProperty(
            name="Partial Payment", description="",
            default=True
        )

        errdisplayguid: PointerProperty(
            name="Display Guid", description="",
            type=bpy.types.Object,
            poll=poll_actors
        )

        chantradius: FloatProperty(
            name="Chant Radius", description="",
            default=100
        )

        particleoffset: FloatVectorProperty(
            name="Particle Offset", description="",
            subtype="XYZ",
            default=(0,0,0)
        )

        particlevalue: FloatProperty(
            name="Particle Value", description="",
            default=0.5
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Asset Lock")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_isready")
                box.prop(self, "has_partialpayment")
                box.prop(self, "has_assetamount")
                box.prop(self, "has_activation")
                box.prop(self, "has_assettype")
                box.prop(self, "has_greetmsg")
                box.prop(self, "has_notreadymsg")
                box.prop(self, "has_lowassetmsg")
                box.prop(self, "has_script")
                box.prop(self, "has_buttonradius")
                box.prop(self, "has_chantradius")
                box.prop(self, "has_linkcomponentguid")
                box.prop(self, "has_multidisplayguid")
                box.prop(self, "has_errdisplayguid")
                box.prop(self, "has_errordelay")
                box.prop(self, "has_particlevalue")
                box.prop(self, "has_particleoffset")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_isready: layout.prop(self, "isready")
            if self.has_partialpayment: layout.prop(self, "partialpayment")
            if self.has_assetamount: layout.prop(self, "assetamount")
            if self.has_activation: layout.prop(self, "activation")
            if self.has_assettype: layout.prop(self, "assettype")
            if self.has_greetmsg: layout.prop(self, "greetmsg")
            if self.has_notreadymsg: layout.prop(self, "notreadymsg")
            if self.has_lowassetmsg: layout.prop(self, "lowassetmsg")
            if self.has_script: layout.prop(self, "script")
            if self.has_buttonradius: layout.prop(self, "buttonradius")
            if self.has_chantradius: layout.prop(self, "chantradius")
            if self.has_linkcomponentguid: layout.prop(self, "linkcomponentguid")
            if self.has_multidisplayguid: layout.prop(self, "multidisplayguid")
            if self.has_errdisplayguid: layout.prop(self, "errdisplayguid")
            if self.has_errordelay: layout.prop(self, "errordelay")
            if self.has_particlevalue: layout.prop(self, "particlevalue")
            if self.has_particleoffset: layout.prop(self, "particleoffset")

        def generate(self, obj):
            tag = f"<assetlock componentguid='{self.componentguid}' "
            if self.has_buttonradius: tag += f"buttonradius='{self.buttonradius}' "
            if self.has_isready: tag += f"isready='{self.isready}' "
            if self.has_assetamount: tag += f"assetamount='{self.assetamount}' "
            if self.has_linkcomponentguid: tag += f"linkcomponentguid='{self.linkcomponentguid}' "
            if self.has_activation: tag += f"activation='{self.activation}' "
            if self.has_script: tag += f"script='{self.script}' "
            if self.has_assettype: tag += f"assettype='{self.assettype}' "
            if self.has_greetmsg: tag += f"greetmsg='{self.greetmsg}' "
            if self.has_notreadymsg: tag += f"notreadymsg='{self.notreadymsg}' "
            if self.has_lowassetmsg: tag += f"lowassetmsg='{self.lowassetmsg}' "
            if self.has_errordelay: tag += f"errordelay='{self.errordelay}' "
            if self.has_multidisplayguid:
                if self.multidisplayguid != None:
                    tag += f"multidisplayguid='{self.multidisplayguid.XinGUID.value}' "
            if self.has_partialpayment: tag += f"partialpayment='{self.partialpayment}' "
            if self.has_errdisplayguid: 
                if self.errdisplayguid != None:
                    tag += f"errdisplayguid='{self.errdisplayguid.XinGUID.value}' "
            if self.has_chantradius: tag += f"chantradius='{self.chantradius}' "
            if self.has_particleoffset: tag += f"particleoffset='{self.particleoffset[0]},{self.particleoffset[1]},{self.particleoffset[2]}' "
            if self.has_particlevalue: tag += f"particlevalue='{self.particlevalue}' "
            tag += "/>"
            return tag
    class SparkleStream(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_amplitudebase: BoolProperty(name="Amplitude Base", description="",default=True)
        has_amplitudedelta: BoolProperty(name="Amplitude Delta", description="",default=True)
        has_intervalbase: BoolProperty(name="Interval Base", description="",default=True)
        has_intervaldelta: BoolProperty(name="Interval Delta", description="",default=True)
        has_scalebase: BoolProperty(name="Scale Base", description="",default=True)
        has_scaledelta: BoolProperty(name="Scale Delta", description="",default=True)
        has_velocitybase: BoolProperty(name="Velocity Base", description="",default=True)
        has_velocitydelta: BoolProperty(name="Velocity Delta", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        amplitudebase: FloatProperty(
            name="Amplitude Base", description="",
            default=1.5
        )

        amplitudedelta: FloatProperty(
            name="Amplitude Delta", description="",
            default=7.5
        )

        intervalbase: FloatProperty(
            name="Interval Base", description="",
            default=0.05
        )

        intervaldelta: FloatProperty(
            name="Interval Delta", description="",
            default=0.03
        )

        scalebase: FloatProperty(
            name="Scale Base", description="",
            default=0.75
        )

        scaledelta: FloatProperty(
            name="Scale Delta", description="",
            default=0.5
        )

        velocitybase: IntProperty(
            name="Velocity Base", description="",
            default=25
        )

        velocitydelta: IntProperty(
            name="Velocity Delta", description="",
            default=10
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Sparkle Stream")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_amplitudebase")
                box.prop(self, "has_amplitudedelta")
                box.prop(self, "has_intervalbase")
                box.prop(self, "has_intervaldelta")
                box.prop(self, "has_scalebase")
                box.prop(self, "has_scaledelta")
                box.prop(self, "has_velocitybase")
                box.prop(self, "has_velocitydelta")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_amplitudebase: layout.prop(self, "amplitudebase")
            if self.has_amplitudedelta: layout.prop(self, "amplitudedelta")
            if self.has_intervalbase: layout.prop(self, "intervalbase")
            if self.has_intervaldelta: layout.prop(self, "intervaldelta")
            if self.has_scalebase: layout.prop(self, "scalebase")
            if self.has_scaledelta: layout.prop(self, "scaledelta")
            if self.has_velocitybase: layout.prop(self, "velocitybase")
            if self.has_velocitydelta: layout.prop(self, "velocitydelta")

        def generate(self, obj):
            tag = f"<sparklestream componentguid='{self.componentguid}' "
            if self.has_amplitudebase: tag += f"amplitudebase='{self.amplitudebase}' "
            if self.has_amplitudedelta: tag += f"amplitudedelta='{self.amplitudedelta}' "
            if self.has_intervalbase: tag += f"intervalbase='{self.intervalbase}' "
            if self.has_intervaldelta: tag += f"intervaldelta='{self.intervaldelta}' "
            if self.has_scalebase: tag += f"scalebase='{self.scalebase}' "
            if self.has_scaledelta: tag += f"scaledelta='{self.scaledelta}' "
            if self.has_velocitybase: tag += f"velocitybase='{self.velocitybase}' "
            if self.has_velocitydelta: tag += f"velocitydelta='{self.velocitydelta}' "
            tag += "/>"
            return tag
    class Weapon(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_power: BoolProperty(name="Power", description="",default=False)
        has_damage: BoolProperty(name="Damage", description="",default=True)
        has_scale: BoolProperty(name="Scale", description="",default=False)
        has_firerate: BoolProperty(name="Fire Rate", description="",default=True)
        has_possessedfirerate: BoolProperty(name="Possessed Fire Rate", description="",default=True)
        has_clipsize: BoolProperty(name="Clip Size", description="",default=True)
        has_possessedclipsize: BoolProperty(name="Possessed Clip Size", description="",default=True)
        has_lethal: BoolProperty(name="Lethal", description="",default=True)
        has_style: BoolProperty(name="Style", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        power: FloatProperty(
            name="Power", description="",
            default=1000
        )

        damage: FloatProperty(
            name="Damage", description="",
            default=10
        )

        scale: FloatProperty(
            name="Scale", description="",
            default=1
        )

        firerate: IntProperty(
            name="Fire Rate", description="",
            default=5
        )

        possessedfirerate: IntProperty(
            name="Possessed Fire Rate", description="",
            default=5
        )

        clipsize: IntProperty(
            name="Clip Size", description="",
            default=40
        )

        possessedclipsize: IntProperty(
            name="Possessed Clip Size", description="",
            default=-1
        )

        lethal: BoolProperty(
            name="Lethal", description="",
            default=False
        )
        
        # This attribute does not exist in the tag template ony in the real data
        style: EnumProperty(
            name="Style", description="",
            items=[
                ("NotAttached","NotAttached","Generated from Real Data"),
                ("SligGun","SligGun","Generated from Real Data"),
                ("CrossBow","CrossBow","Generated from Real Data")
            ]
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Weapon")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_power")
                box.prop(self, "has_damage")
                box.prop(self, "has_scale")
                box.prop(self, "has_firerate")
                box.prop(self, "has_possessedfirerate")
                box.prop(self, "has_clipsize")
                box.prop(self, "has_possessedclipsize")
                box.prop(self, "has_lethal")
                box.prop(self, "has_style")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_power: layout.prop(self, "power")
            if self.has_damage: layout.prop(self, "damage")
            if self.has_scale: layout.prop(self, "scale")
            if self.has_firerate: layout.prop(self, "firerate")
            if self.has_possessedfirerate: layout.prop(self, "possessedfirerate")
            if self.has_clipsize: layout.prop(self, "clipsize")
            if self.has_possessedclipsize: layout.prop(self, "possessedclipsize")
            if self.has_lethal: layout.prop(self, "lethal")
            if self.has_style: layout.prop(self, "style")

        def generate(self, obj):
            tag = f"<weapon componentguid='{self.componentguid}' "
            if self.has_power: tag += f"power='{self.power}' "
            if self.has_damage: tag += f"damage='{self.damage}' "
            if self.has_scale: tag += f"scale='{self.scale}' "
            if self.has_firerate: tag += f"firerate='{self.firerate}' "
            if self.has_possessedfirerate: tag += f"possessedfirerate='{self.possessedfirerate}' "
            if self.has_clipsize: tag += f"clipsize='{self.clipsize}' "
            if self.has_possessedclipsize: tag += f"possessedclipsize='{self.possessedclipsize}' "
            if self.has_lethal: tag += f"lethal='{self.lethal}' "
            if self.has_style: tag += f"style='{self.style}' "
            tag += "/>"
            return tag
    class Broadcaster(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_link: BoolProperty(name="Link", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        link: StringProperty(
            name="Link", description="",
            default=""
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Broadcaster")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_link")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_link: layout.prop(self, "link")

        def generate(self, obj):
            tag = f"<broadcaster componentguid='{self.componentguid}' "
            if self.has_link: tag += f"link='{self.link}' "
            tag += "/>"
            return tag
    class Collectable(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_initialstate: BoolProperty(name="Initial State", description="",default=True)
        has_health: BoolProperty(name="Health", description="",default=True)
        has_reward: BoolProperty(name="Reward", description="",default=False)
        has_radius: BoolProperty(name="Radius", description="",default=False)
        has_type: BoolProperty(name="Type", description="",default=False)
        has_growthreshold: BoolProperty(name="Growth Threshold", description="",default=False)
        has_growcount: BoolProperty(name="Grow Count", description="",default=False)
        has_growinterval: BoolProperty(name="Grow Interval", description="",default=False)

        def update_initialstate(self, context):
            update_mesh(context)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        reward: IntProperty(
            name="Reward", description="",
            default=1
        )

        health: IntProperty(
            name="Health", description="",
            default=0
        )

        radius: FloatProperty(
            name="Radius", description="",
            default=8
        )

        type: EnumProperty(
            name="Type", description="",
            items=[
                ("Humshrub","Humshrub","Generated default with script"),
                ("Toxic Spore","Toxic Spore","Found in TagTemplate"),
                ("Moolah Bag","Moolah Bag","Found in TagTemplate")
            ],
            default="Humshrub"
        )

        growthreshold: IntProperty(
            name="Growth Threshold", description="",
            default=0
        )

        growcount: IntProperty(
            name="Grow Count", description="",
            default=-1
        )

        growinterval: FloatProperty(
            name="Grow Interval", description="",
            default=1
        )

        initialstate: EnumProperty(
            name="Initial State", description="",
            items=[
                ("Grown","Grown","Generated default with script"),
                ("Not Grown","Not Grown","Found in TagTemplate"),
                ("Dead","Dead","Generated from Real Data")
            ],
            default="Grown",
            update=update_initialstate
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Collectable")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_initialstate")
                box.prop(self, "has_health")
                box.prop(self, "has_reward")
                box.prop(self, "has_radius")
                box.prop(self, "has_type")
                box.prop(self, "has_growthreshold")
                box.prop(self, "has_growcount")
                box.prop(self, "has_growinterval")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_initialstate: layout.prop(self, "initialstate")
            if self.has_health: layout.prop(self, "health")
            if self.has_reward: layout.prop(self, "reward")
            if self.has_radius: layout.prop(self, "radius")
            if self.has_type: layout.prop(self, "type")
            if self.has_growthreshold: layout.prop(self, "growthreshold")
            if self.has_growcount: layout.prop(self, "growcount")
            if self.has_growinterval: layout.prop(self, "growinterval")

        def generate(self, obj):
            tag = f"<collectable componentguid='{self.componentguid}' "
            if self.has_reward: tag += f"reward='{self.reward}' "
            if self.has_health: tag += f"health='{self.health}' "
            if self.has_radius: tag += f"radius='{self.radius}' "
            if self.has_type: tag += f"type='{self.type}' "
            if self.has_growthreshold: tag += f"growthreshold='{self.growthreshold}' "
            if self.has_growcount: tag += f"growcount='{self.growcount}' "
            if self.has_growinterval: tag += f"growinterval='{self.growinterval}' "
            if self.has_initialstate: tag += f"initialstate='{self.initialstate}' "
            tag += f"position='{genPos(obj.location)}' "
            tag += "/>"
            return tag
    class PowerUp(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_key: BoolProperty(name="Key", description="",default=True)
        has_timeout: BoolProperty(name="Time Out", description="",default=True)
        has_warning: BoolProperty(name="Warning", description="",default=False)
        has_bouncedist: BoolProperty(name="Bounce Dist", description="",default=True)
        has_buttoffset: BoolProperty(name="Butt Offset", description="",default=False)
        has_carryaccel: BoolProperty(name="Carry Accel", description="",default=False)
        has_carrydecel: BoolProperty(name="Carry Decel", description="",default=False)
        has_carrymax: BoolProperty(name="Carry Max", description="",default=True)
        has_carrymin: BoolProperty(name="Carry Min", description="",default=False)
        has_getup: BoolProperty(name="Get Up", description="",default=False)
        has_joyrunmin: BoolProperty(name="Joy Stick Run Min", description="",default=False)
        has_joystandmax: BoolProperty(name="Joy Stick Stand Max", description="",default=False)
        has_joytiptoemax: BoolProperty(name="Joy Stick Tip Toe Max", description="",default=False)
        has_joytiptoemin: BoolProperty(name="Joy Stick Tip Toe Min", description="",default=False)
        has_joywalkmax: BoolProperty(name="Joy Stick Walk Max", description="",default=False)
        has_joywalkmin: BoolProperty(name="Joy Stick Walk Min", description="",default=False)
        has_jumpheight: BoolProperty(name="Jump Height", description="",default=True)
        has_knockback: BoolProperty(name="Knockback", description="",default=False)
        has_knockbackdecel: BoolProperty(name="Knockback Decel", description="",default=False)
        has_knockthresh: BoolProperty(name="Knock Thresh", description="",default=False)
        has_landdist: BoolProperty(name="Land Dist", description="",default=True)
        has_launchspeed: BoolProperty(name="Launch Speed", description="",default=False)
        has_mass: BoolProperty(name="Mass", description="",default=False)
        has_maxbounceheight: BoolProperty(name="Max Bounce Height", description="",default=False)
        has_maxincline: BoolProperty(name="Max Incline", description="",default=False)
        has_maxstep: BoolProperty(name="Max Step", description="",default=False)
        has_maxtransition: BoolProperty(name="Max Transition", description="",default=False)
        has_minbounceheight: BoolProperty(name="Min Bounce Height", description="",default=False)
        has_runaccel: BoolProperty(name="Run Accel", description="",default=False)
        has_rundecel: BoolProperty(name="Run Decel", description="",default=False)
        has_runmax: BoolProperty(name="Run Max", description="",default=True)
        has_runmin: BoolProperty(name="Run Min", description="",default=True)
        has_skiddecel: BoolProperty(name="Skid Decel", description="",default=False)
        has_slideaccel: BoolProperty(name="Slide Accel", description="",default=False)
        has_slidedecel: BoolProperty(name="Slide Decel", description="",default=False)
        has_slideangle: BoolProperty(name="Slide Angle", description="",default=False)
        has_slidemax: BoolProperty(name="Slide Max", description="",default=False)
        has_slidemin: BoolProperty(name="Slide Min", description="",default=False)
        has_slidepct: BoolProperty(name="Slide Pct", description="",default=False)
        has_slideuphill: BoolProperty(name="Slide Up Hill", description="",default=False)
        has_slidesteep: BoolProperty(name="Slide Steep", description="",default=False)
        has_tiptoeaccel: BoolProperty(name="Tip Toe Accel", description="",default=False)
        has_tiptoedecel: BoolProperty(name="Tip Toe Decel", description="",default=False)
        has_tiptoemax: BoolProperty(name="Tip Toe Max", description="",default=True)
        has_tiptoemin: BoolProperty(name="Tip Toe Min", description="",default=True)
        has_toss: BoolProperty(name="Toss", description="",default=False)
        has_tossup: BoolProperty(name="Toss Up", description="",default=False)
        has_turnangle: BoolProperty(name="Turn Angle", description="",default=False)
        has_walkaccel: BoolProperty(name="Walk Accel", description="",default=False)
        has_walkdecel: BoolProperty(name="Walk Decel", description="",default=False)
        has_walkmax: BoolProperty(name="Walk Max", description="",default=True)
        has_walkmin: BoolProperty(name="Walk Min", description="",default=True)
        has_zapattack: BoolProperty(name="Zap Attack", description="",default=True)
        has_invisibility: BoolProperty(name="Invisibility", description="",default=True)
        has_fadealpha: BoolProperty(name="Fade Alpha", description="",default=False)
        has_fadeouttime: BoolProperty(name="Fade Out Time", description="",default=False)
        has_fadeintimenormal: BoolProperty(name="Fade In Time Normal", description="",default=False)
        has_fadeintimeabort: BoolProperty(name="Fade In Time Abort", description="",default=False)
        has_waterjumpheight: BoolProperty(name="Water Jump Height", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        key: IntProperty(
            name="Key", description="",
            default=0
        )

        timeout: FloatProperty(
            name="Time Out", description="",
            default=0
        )

        warning: FloatProperty(
            name="Warning", description="",
            default=5
        )

        bouncedist: FloatProperty(
            name="Bounce Dist", description="",
            default=0
        )

        buttoffset: FloatProperty(
            name="Butt Offset", description="",
            default=0
        )

        carryaccel: FloatProperty(
            name="Carry Accel", description="",
            default=0
        )

        carrydecel: FloatProperty(
            name="Carry Decel", description="",
            default=0
        )

        carrymax: FloatProperty(
            name="Carry Max", description="",
            default=0
        )

        carrymin: FloatProperty(
            name="Carry Min", description="",
            default=0
        )

        getup: FloatProperty(
            name="Get Up", description="",
            default=0
        )

        joyrunmin: FloatProperty(
            name="Joy Stick Run Min", description="",
            default=0
        )

        joystandmax: FloatProperty(
            name="Joy Stick Stand Max", description="",
            default=0
        )

        joytiptoemax: FloatProperty(
            name="Joy Stick Tip Toe Max", description="",
            default=0
        )

        joytiptoemin: FloatProperty(
            name="Joy Stick Tip Toe Min", description="",
            default=0
        )

        joywalkmax: FloatProperty(
            name="Joy Stick Walk Max", description="",
            default=0
        )

        joywalkmin: FloatProperty(
            name="Joy Stick Walk Min", description="",
            default=0
        )

        jumpheight: FloatProperty(
            name="Jump Height", description="",
            default=0
        )

        knockback: FloatProperty(
            name="Knockback", description="",
            default=0
        )

        knockbackdecel: FloatProperty(
            name="Knockback Decel", description="",
            default=0
        )

        knockthresh: FloatProperty(
            name="Knock Thresh", description="",
            default=0
        )

        landdist: FloatProperty(
            name="Land Dist", description="",
            default=0
        )

        launchspeed: FloatProperty(
            name="Launch Speed", description="",
            default=0
        )

        mass: FloatProperty(
            name="Mass", description="",
            default=0
        )

        maxbounceheight: FloatProperty(
            name="Max Bounce Height", description="",
            default=0
        )

        maxincline: FloatProperty(
            name="Max Incline", description="",
            default=0
        )

        maxstep: FloatProperty(
            name="Max Step", description="",
            default=0
        )

        maxtransition: FloatProperty(
            name="Max Transition", description="",
            default=0
        )

        minbounceheight: FloatProperty(
            name="Min Bounce Height", description="",
            default=0
        )

        runaccel: FloatProperty(
            name="Run Accel", description="",
            default=0
        )

        rundecel: FloatProperty(
            name="Run Decel", description="",
            default=0
        )

        runmax: FloatProperty(
            name="Run Max", description="",
            default=0
        )

        runmin: FloatProperty(
            name="Run Min", description="",
            default=0
        )

        skiddecel: FloatProperty(
            name="Skid Decel", description="",
            default=0
        )

        slideaccel: FloatProperty(
            name="Slide Accel", description="",
            default=0
        )

        slidedecel: FloatProperty(
            name="Slide Decel", description="",
            default=0
        )

        slideangle: FloatProperty(
            name="Slide Angle", description="",
            default=0
        )

        slidemax: FloatProperty(
            name="Slide Max", description="",
            default=0
        )

        slidemin: FloatProperty(
            name="Slide Min", description="",
            default=0
        )

        slidepct: FloatProperty(
            name="Slide Pct", description="",
            default=0
        )

        slideuphill: FloatProperty(
            name="Slide Up Hill", description="",
            default=0
        )

        slidesteep: FloatProperty(
            name="Slide Steep", description="",
            default=0
        )

        tiptoeaccel: FloatProperty(
            name="Tip Toe Accel", description="",
            default=0
        )

        tiptoedecel: FloatProperty(
            name="Tip Toe Decel", description="",
            default=0
        )

        tiptoemax: FloatProperty(
            name="Tip Toe Max", description="",
            default=0
        )

        tiptoemin: FloatProperty(
            name="Tip Toe Min", description="",
            default=0
        )

        toss: FloatProperty(
            name="Toss", description="",
            default=0
        )

        tossup: FloatProperty(
            name="Toss Up", description="",
            default=0
        )

        turnangle: FloatProperty(
            name="Turn Angle", description="",
            default=0
        )

        walkaccel: FloatProperty(
            name="Walk Accel", description="",
            default=0
        )

        walkdecel: FloatProperty(
            name="Walk Decel", description="",
            default=0
        )

        walkmax: FloatProperty(
            name="Walk Max", description="",
            default=0
        )

        walkmin: FloatProperty(
            name="Walk Min", description="",
            default=0
        )

        zapattack: BoolProperty(
            name="Zap Attack", description="",
            default=False
        )

        invisibility: BoolProperty(
            name="Invisibility", description="",
            default=False
        )

        fadealpha: FloatProperty(
            name="Fade Alpha", description="",
            default=0.3
        )

        fadeouttime: FloatProperty(
            name="Fade Out Time", description="",
            default=1
        )

        fadeintimenormal: FloatProperty(
            name="Fade In Time Normal", description="",
            default=3
        )

        fadeintimeabort: FloatProperty(
            name="Fade In Time Abort", description="",
            default=0.5
        )

        waterjumpheight: FloatProperty(
            name="Water Jump Height", description="",
            default=0
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Power Up")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_key")
                box.prop(self, "has_timeout")
                box.prop(self, "has_warning")
                box.prop(self, "has_bouncedist")
                box.prop(self, "has_buttoffset")
                box.prop(self, "has_carryaccel")
                box.prop(self, "has_carrydecel")
                box.prop(self, "has_carrymax")
                box.prop(self, "has_carrymin")
                box.prop(self, "has_getup")
                box.prop(self, "has_joyrunmin")
                box.prop(self, "has_joystandmax")
                box.prop(self, "has_joytiptoemax")
                box.prop(self, "has_joytiptoemin")
                box.prop(self, "has_joywalkmax")
                box.prop(self, "has_joywalkmin")
                box.prop(self, "has_jumpheight")
                box.prop(self, "has_knockback")
                box.prop(self, "has_knockbackdecel")
                box.prop(self, "has_knockthresh")
                box.prop(self, "has_landdist")
                box.prop(self, "has_launchspeed")
                box.prop(self, "has_mass")
                box.prop(self, "has_maxbounceheight")
                box.prop(self, "has_maxincline")
                box.prop(self, "has_maxstep")
                box.prop(self, "has_maxtransition")
                box.prop(self, "has_minbounceheight")
                box.prop(self, "has_runaccel")
                box.prop(self, "has_rundecel")
                box.prop(self, "has_runmax")
                box.prop(self, "has_runmin")
                box.prop(self, "has_skiddecel")
                box.prop(self, "has_slideaccel")
                box.prop(self, "has_slidedecel")
                box.prop(self, "has_slideangle")
                box.prop(self, "has_slidemax")
                box.prop(self, "has_slidemin")
                box.prop(self, "has_slidepct")
                box.prop(self, "has_slideuphill")
                box.prop(self, "has_slidesteep")
                box.prop(self, "has_tiptoeaccel")
                box.prop(self, "has_tiptoedecel")
                box.prop(self, "has_tiptoemax")
                box.prop(self, "has_tiptoemin")
                box.prop(self, "has_toss")
                box.prop(self, "has_tossup")
                box.prop(self, "has_turnangle")
                box.prop(self, "has_walkaccel")
                box.prop(self, "has_walkdecel")
                box.prop(self, "has_walkmax")
                box.prop(self, "has_walkmin")
                box.prop(self, "has_zapattack")
                box.prop(self, "has_invisibility")
                box.prop(self, "has_fadealpha")
                box.prop(self, "has_fadeouttime")
                box.prop(self, "has_fadeintimenormal")
                box.prop(self, "has_fadeintimeabort")
                box.prop(self, "has_waterjumpheight")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_key: layout.prop(self, "key")
            if self.has_timeout: layout.prop(self, "timeout")
            if self.has_warning: layout.prop(self, "warning")
            if self.has_bouncedist: layout.prop(self, "bouncedist")
            if self.has_buttoffset: layout.prop(self, "buttoffset")
            if self.has_carryaccel: layout.prop(self, "carryaccel")
            if self.has_carrydecel: layout.prop(self, "carrydecel")
            if self.has_carrymax: layout.prop(self, "carrymax")
            if self.has_carrymin: layout.prop(self, "carrymin")
            if self.has_getup: layout.prop(self, "getup")
            if self.has_joyrunmin: layout.prop(self, "joyrunmin")
            if self.has_joystandmax: layout.prop(self, "joystandmax")
            if self.has_joytiptoemax: layout.prop(self, "joytiptoemax")
            if self.has_joytiptoemin: layout.prop(self, "joytiptoemin")
            if self.has_joywalkmax: layout.prop(self, "joywalkmax")
            if self.has_joywalkmin: layout.prop(self, "joywalkmin")
            if self.has_jumpheight: layout.prop(self, "jumpheight")
            if self.has_knockback: layout.prop(self, "knockback")
            if self.has_knockbackdecel: layout.prop(self, "knockbackdecel")
            if self.has_knockthresh: layout.prop(self, "knockthresh")
            if self.has_landdist: layout.prop(self, "landdist")
            if self.has_launchspeed: layout.prop(self, "launchspeed")
            if self.has_mass: layout.prop(self, "mass")
            if self.has_maxbounceheight: layout.prop(self, "maxbounceheight")
            if self.has_maxincline: layout.prop(self, "maxincline")
            if self.has_maxstep: layout.prop(self, "maxstep")
            if self.has_maxtransition: layout.prop(self, "maxtransition")
            if self.has_minbounceheight: layout.prop(self, "minbounceheight")
            if self.has_runaccel: layout.prop(self, "runaccel")
            if self.has_rundecel: layout.prop(self, "rundecel")
            if self.has_runmax: layout.prop(self, "runmax")
            if self.has_runmin: layout.prop(self, "runmin")
            if self.has_skiddecel: layout.prop(self, "skiddecel")
            if self.has_slideaccel: layout.prop(self, "slideaccel")
            if self.has_slidedecel: layout.prop(self, "slidedecel")
            if self.has_slideangle: layout.prop(self, "slideangle")
            if self.has_slidemax: layout.prop(self, "slidemax")
            if self.has_slidemin: layout.prop(self, "slidemin")
            if self.has_slidepct: layout.prop(self, "slidepct")
            if self.has_slideuphill: layout.prop(self, "slideuphill")
            if self.has_slidesteep: layout.prop(self, "slidesteep")
            if self.has_tiptoeaccel: layout.prop(self, "tiptoeaccel")
            if self.has_tiptoedecel: layout.prop(self, "tiptoedecel")
            if self.has_tiptoemax: layout.prop(self, "tiptoemax")
            if self.has_tiptoemin: layout.prop(self, "tiptoemin")
            if self.has_toss: layout.prop(self, "toss")
            if self.has_tossup: layout.prop(self, "tossup")
            if self.has_turnangle: layout.prop(self, "turnangle")
            if self.has_walkaccel: layout.prop(self, "walkaccel")
            if self.has_walkdecel: layout.prop(self, "walkdecel")
            if self.has_walkmax: layout.prop(self, "walkmax")
            if self.has_walkmin: layout.prop(self, "walkmin")
            if self.has_zapattack: layout.prop(self, "zapattack")
            if self.has_invisibility: layout.prop(self, "invisibility")
            if self.has_fadealpha: layout.prop(self, "fadealpha")
            if self.has_fadeouttime: layout.prop(self, "fadeouttime")
            if self.has_fadeintimenormal: layout.prop(self, "fadeintimenormal")
            if self.has_fadeintimeabort: layout.prop(self, "fadeintimeabort")
            if self.has_waterjumpheight: layout.prop(self, "waterjumpheight")

        def generate(self, obj):
            tag = f"<powerup componentguid='{self.componentguid}' "
            if self.has_key: tag += f"key='{self.key}' "
            if self.has_timeout: tag += f"timeout='{self.timeout}' "
            if self.has_warning: tag += f"warning='{self.warning}' "
            if self.has_bouncedist: tag += f"bouncedist='{self.bouncedist}' "
            if self.has_buttoffset: tag += f"buttoffset='{self.buttoffset}' "
            if self.has_carryaccel: tag += f"carryaccel='{self.carryaccel}' "
            if self.has_carrydecel: tag += f"carrydecel='{self.carrydecel}' "
            if self.has_carrymax: tag += f"carrymax='{self.carrymax}' "
            if self.has_carrymin: tag += f"carrymin='{self.carrymin}' "
            if self.has_getup: tag += f"getup='{self.getup}' "
            if self.has_joyrunmin: tag += f"joyrunmin='{self.joyrunmin}' "
            if self.has_joystandmax: tag += f"joystandmax='{self.joystandmax}' "
            if self.has_joytiptoemax: tag += f"joytiptoemax='{self.joytiptoemax}' "
            if self.has_joytiptoemin: tag += f"joytiptoemin='{self.joytiptoemin}' "
            if self.has_joywalkmax: tag += f"joywalkmax='{self.joywalkmax}' "
            if self.has_joywalkmin: tag += f"joywalkmin='{self.joywalkmin}' "
            if self.has_jumpheight: tag += f"jumpheight='{self.jumpheight}' "
            if self.has_knockback: tag += f"knockback='{self.knockback}' "
            if self.has_knockbackdecel: tag += f"knockbackdecel='{self.knockbackdecel}' "
            if self.has_knockthresh: tag += f"knockthresh='{self.knockthresh}' "
            if self.has_landdist: tag += f"landdist='{self.landdist}' "
            if self.has_launchspeed: tag += f"launchspeed='{self.launchspeed}' "
            if self.has_mass: tag += f"mass='{self.mass}' "
            if self.has_maxbounceheight: tag += f"maxbounceheight='{self.maxbounceheight}' "
            if self.has_maxincline: tag += f"maxincline='{self.maxincline}' "
            if self.has_maxstep: tag += f"maxstep='{self.maxstep}' "
            if self.has_maxtransition: tag += f"maxtransition='{self.maxtransition}' "
            if self.has_minbounceheight: tag += f"minbounceheight='{self.minbounceheight}' "
            if self.has_runaccel: tag += f"runaccel='{self.runaccel}' "
            if self.has_rundecel: tag += f"rundecel='{self.rundecel}' "
            if self.has_runmax: tag += f"runmax='{self.runmax}' "
            if self.has_runmin: tag += f"runmin='{self.runmin}' "
            if self.has_skiddecel: tag += f"skiddecel='{self.skiddecel}' "
            if self.has_slideaccel: tag += f"slideaccel='{self.slideaccel}' "
            if self.has_slidedecel: tag += f"slidedecel='{self.slidedecel}' "
            if self.has_slideangle: tag += f"slideangle='{self.slideangle}' "
            if self.has_slidemax: tag += f"slidemax='{self.slidemax}' "
            if self.has_slidemin: tag += f"slidemin='{self.slidemin}' "
            if self.has_slidepct: tag += f"slidepct='{self.slidepct}' "
            if self.has_slideuphill: tag += f"slideuphill='{self.slideuphill}' "
            if self.has_slidesteep: tag += f"slidesteep='{self.slidesteep}' "
            if self.has_tiptoeaccel: tag += f"tiptoeaccel='{self.tiptoeaccel}' "
            if self.has_tiptoedecel: tag += f"tiptoedecel='{self.tiptoedecel}' "
            if self.has_tiptoemax: tag += f"tiptoemax='{self.tiptoemax}' "
            if self.has_tiptoemin: tag += f"tiptoemin='{self.tiptoemin}' "
            if self.has_toss: tag += f"toss='{self.toss}' "
            if self.has_tossup: tag += f"tossup='{self.tossup}' "
            if self.has_turnangle: tag += f"turnangle='{self.turnangle}' "
            if self.has_walkaccel: tag += f"walkaccel='{self.walkaccel}' "
            if self.has_walkdecel: tag += f"walkdecel='{self.walkdecel}' "
            if self.has_walkmax: tag += f"walkmax='{self.walkmax}' "
            if self.has_walkmin: tag += f"walkmin='{self.walkmin}' "
            if self.has_zapattack: tag += f"zapattack='{self.zapattack}' "
            if self.has_invisibility: tag += f"invisibility='{self.invisibility}' "
            if self.has_fadealpha: tag += f"fadealpha='{self.fadealpha}' "
            if self.has_fadeouttime: tag += f"fadeouttime='{self.fadeouttime}' "
            if self.has_fadeintimenormal: tag += f"fadeintimenormal='{self.fadeintimenormal}' "
            if self.has_fadeintimeabort: tag += f"fadeintimeabort='{self.fadeintimeabort}' "
            if self.has_waterjumpheight: tag += f"waterjumpheight='{self.waterjumpheight}' "
            tag += "/>"
            return tag
    class Shadow(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_method: BoolProperty(name="Method", description="",default=True)
        has_maxshadows: BoolProperty(name="Max Shadows", description="",default=True)
        has_direction: BoolProperty(name="Direction", description="",default=True)
        has_opacity: BoolProperty(name="Opacity", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        method: EnumProperty(
            name="Method", description="",
            items=[
                ("fixed","fixed","Generated default with script"),
                ("variable","variable","Generated from Real Data"),
                ("polygonal","polygonal","Generated from Real Data")
            ],
            default="fixed"
        )

        maxshadows: BoolProperty(
            name="Max Shadows", description="",
            default=1
        )

        direction: FloatVectorProperty(
            name="Direction", description="",
            subtype="XYZ",
            default=(0,0,-1)
        )

        opacity: StringProperty(
            name="Opacity", description="",
            default="0.7"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Shadow")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_method")
                box.prop(self, "has_maxshadows")
                box.prop(self, "has_direction")
                box.prop(self, "has_opacity")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_method: layout.prop(self, "method")
            if self.has_maxshadows: layout.prop(self, "maxshadows")
            if self.has_direction: layout.prop(self, "direction")
            if self.has_opacity: layout.prop(self, "opacity")

        def generate(self, obj):
            tag = f"<shadow componentguid='{self.componentguid}' "
            if self.has_method: tag += f"method='{self.method}' "
            if self.has_maxshadows: tag += f"maxshadows='{self.maxshadows}' "
            if self.has_direction: tag += f"direction='{self.direction[0]},{self.direction[1]},{self.direction[2]}' "
            if self.has_opacity: tag += f"opacity='{self.opacity}' "
            tag += "/>"
            return tag
    class LifeCycle(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_health: BoolProperty(name="Health", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        health: IntProperty(
            name="Health", description="",
            default=500
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Life Cycle")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_health")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_health: layout.prop(self, "health")

        def generate(self, obj):
            tag = f"<lifecycle componentguid='{self.componentguid}' "
            if self.has_health: tag += f"health='{self.health}' "
            tag += "/>"
            return tag
    class Explosion(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_explosiontype: BoolProperty(name="Explosion Type", description="",default=True)
        has_propagations: BoolProperty(name="Propagations", description="",default=True)
        has_contact: BoolProperty(name="Contact", description="",default=True)
        has_damageradius: BoolProperty(name="Damage Radius", description="",default=True)
        has_objectradius: BoolProperty(name="Object Radius", description="",default=True)
        has_damageval: BoolProperty(name="Damage Val", description="",default=True)
        has_createactive: BoolProperty(name="Create Active", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        explosiontype: EnumProperty(
            name="Explosion Type", description="",
            items=[
                ("DefaultExplosion","DefaultExplosion","Generated default with script"),
                ("DefaultCrateExplosion","Default Crate Explosion","Found in TagTemplate"),
                ("LandMineExplosion","Land Mine Explosion","Found in TagTemplate"),
                ("BonepowderCrateExplosion","Bonepowder Crate Explosion","Generated from Real Data"),
                ("ExplodingCrateExplosion","Exploding Crate Explosion","Generated from Real Data"),
                ("TetheredMineExplosion","Tethered Mine Explosion","Generated from Real Data"),
                ("FreeFloatingMineExplosion","Free Floating Mine Explosion","Found in TagTemplate"),
                ("EggCrateExplosion","Egg Crate Explosion","Generated from Real Data"),
                ("RG8bPowerfulExplosion","RG8b Powerful Explosion","Generated from Real Data"),
                ("RG2RM4WideExplosion","RG2RM4 Wide Explosion","Generated from Real Data")
            ],
            default="DefaultExplosion"
        )

        propagations: IntProperty(
            name="Propagations", description="",
            default=0
        )

        contact: BoolProperty(
            name="Contact", description="",
            default=False
        )

        damageradius: FloatProperty(
            name="Damage Radius", description="",
            default=0
        )

        objectradius: FloatProperty(
            name="Object Radius", description="",
            default=0
        )

        damageval: IntProperty(
            name="Damage Val", description="",
            default=0
        )

        createactive: BoolProperty(
            name="Create Active", description="",
            default=False
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Explosion")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_explosiontype")
                box.prop(self, "has_propagations")
                box.prop(self, "has_contact")
                box.prop(self, "has_damageradius")
                box.prop(self, "has_objectradius")
                box.prop(self, "has_damageval")
                box.prop(self, "has_createactive")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_explosiontype: layout.prop(self, "explosiontype")
            if self.has_propagations: layout.prop(self, "propagations")
            if self.has_contact: layout.prop(self, "contact")
            if self.has_damageradius: layout.prop(self, "damageradius")
            if self.has_objectradius: layout.prop(self, "objectradius")
            if self.has_damageval: layout.prop(self, "damageval")
            if self.has_createactive: layout.prop(self, "createactive")

        def generate(self, obj):
            tag = f"<explosion componentguid='{self.componentguid}' "
            if self.has_explosiontype: tag += f"explosiontype='{self.explosiontype}' "
            if self.has_propagations: tag += f"propagations='{self.propagations}' "
            if self.has_contact: tag += f"contact='{self.contact}' "
            if self.has_damageradius: tag += f"damageradius='{self.damageradius}' "
            if self.has_objectradius: tag += f"objectradius='{self.objectradius}' "
            if self.has_damageval: tag += f"damageval='{self.damageval}' "
            if self.has_createactive: tag += f"createactive='{self.createactive}' "
            tag += "/>"
            return tag
    class Target(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_cameraid: BoolProperty(name="Camera", description="",default=True)
        has_guid: BoolProperty(name="Target", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        cameraid: PointerProperty(
            name="Camera", description="", 
            type=bpy.types.Object,
            poll=poll_cameras
        )

        guid: PointerProperty(
            name="Target", description="",
            type=bpy.types.Object
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Target")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_cameraid")
                box.prop(self, "has_guid")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_cameraid: layout.prop(self, "cameraid")
            if self.has_guid: layout.prop(self, "guid")

        def generate(self, obj):
            tag = f"<target componentguid='{self.componentguid}' "
            if self.has_cameraid: 
                if self.cameraid != None:
                    tag += f"cameraid='{self.cameraid.XinGUID.value}' "
            if self.has_guid: 
                if self.guid != None:
                    tag += f"guid='{self.guid.XinGUID.guid}' "
            tag += "/>"
            return tag
    class Bullseye(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_offset: BoolProperty(name="Offset", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        offset: FloatVectorProperty(
            name="Offset", description="",
            subtype="XYZ",
            default=(0,0,0)
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Bullseye")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_offset")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_offset: layout.prop(self, "offset")

        def generate(self, obj):
            tag = f"<bullseye componentguid='{self.componentguid}' "
            if self.has_offset: tag += f"offset='{self.offset[0]},{self.offset[1]},{self.offset[2]}' "
            tag += "/>"
            return tag
    class ShortGoal(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_walk: BoolProperty(name="Walk", description="",default=False)
        has_ladder: BoolProperty(name="Ladder", description="",default=False)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        walk: BoolProperty(
            name="Walk", description="",
            default=True
        )

        ladder: BoolProperty(
            name="Ladder", description="",
            default=True
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Short Goal")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_walk")
                box.prop(self, "has_ladder")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_walk: layout.prop(self, "walk")
            if self.has_ladder: layout.prop(self, "ladder")

        def generate(self, obj):
            tag = f"<shortgoal componentguid='{self.componentguid}' "
            if self.has_walk: tag += f"walk='{self.walk}' "
            if self.has_ladder: tag += f"ladder='{self.ladder}' "
            tag += "/>"
            return tag
    class Transformer(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_flavortotransform: BoolProperty(name="Flavor To Transform", description="",default=True)
        has_transformplayer: BoolProperty(name="Transform Player", description="",default=True)
        has_prototypeguid: BoolProperty(name="Prototype", description="",default=True)
        has_activationoffset: BoolProperty(name="Activation Offset", description="",default=True)
        has_activationheight: BoolProperty(name="Activation Height", description="",default=True)
        has_activationrange: BoolProperty(name="Activation Range", description="",default=True)
        has_activationangle: BoolProperty(name="Activation Angle", description="",default=True)
        has_assetcomponent: BoolProperty(name="Asset Component", description="",default=True)
        has_transformseconds: BoolProperty(name="Transform Seconds", description="",default=False)
        has_betweenseconds: BoolProperty(name="Seconds", description="",default=False)
        has_zapstart: BoolProperty(name="Zap Start", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        flavortotransform: EnumProperty(
            name="Flavor To Transform", description="",
            items=[
                ("native","Native","Generated default with script"),
                ("tomohawker","Tomohawker","Generated from Real Data"),
                ("worker","Worker","Generated from Real Data"),
                ("archer","Archer","Found in TagTemplate"),
                ("abe","Abe","Found in TagTemplate"),
                ("slig","Slig","Found in TagTemplate"),
                ("bigbro","Bigbro","Found in TagTemplate"),
                ("fuzzle","Fuzzle","Found in TagTemplate"),
                ("intern","Intern","Found in TagTemplate"),
                ("glukkon","Glukkon","Found in TagTemplate"),
            ],
            default="native"
        )

        transformplayer: BoolProperty(
            name="Transform Player", description="",
            default=False
        )

        prototypeguid: PointerProperty(
            name="Prototype", description="",
            type=bpy.types.Object
        )

        activationoffset: FloatProperty(
            name="Activation Offset", description="",
            default=-90
        )

        activationheight: FloatProperty(
            name="Activation Height", description="",
            default=120
        )

        activationrange: FloatProperty(
            name="Activation Range", description="",
            default=100
        )

        activationangle: FloatProperty(
            name="Activation Angle", description="",
            default=360
        )

        assetcomponent: IntProperty(
            name="Asset Component", description="",
            default=0
        )

        transformseconds: FloatProperty(
            name="Transform Seconds", description="",
            default=0.4
        )

        betweenseconds: FloatProperty(
            name="Seconds", description="",
            default=0
        )

        zapstart: FloatVectorProperty(
            name="Zap Start", description="",
            subtype="XYZ",
            default=(0,0,0)
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Transformer")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_flavortotransform")
                box.prop(self, "has_transformplayer")
                box.prop(self, "has_prototypeguid")
                box.prop(self, "has_activationoffset")
                box.prop(self, "has_activationheight")
                box.prop(self, "has_activationrange")
                box.prop(self, "has_activationangle")
                box.prop(self, "has_assetcomponent")
                box.prop(self, "has_transformseconds")
                box.prop(self, "has_betweenseconds")
                box.prop(self, "has_zapstart")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_flavortotransform: layout.prop(self, "flavortotransform")
            if self.has_transformplayer: layout.prop(self, "transformplayer")
            if self.has_prototypeguid: layout.prop(self, "prototypeguid")
            if self.has_activationoffset: layout.prop(self, "activationoffset")
            if self.has_activationheight: layout.prop(self, "activationheight")
            if self.has_activationrange: layout.prop(self, "activationrange")
            if self.has_activationangle: layout.prop(self, "activationangle")
            if self.has_assetcomponent: layout.prop(self, "assetcomponent")
            if self.has_transformseconds: layout.prop(self, "transformseconds")
            if self.has_betweenseconds: layout.prop(self, "betweenseconds")
            if self.has_zapstart: layout.prop(self, "zapstart")

        def generate(self, obj):
            tag = f"<transformer componentguid='{self.componentguid}' "
            if self.has_flavortotransform: tag += f"flavortotransform='{self.flavortotransform}' "
            if self.has_transformplayer: tag += f"transformplayer='{self.transformplayer}' "
            if self.has_prototypeguid: 
                if self.prototypeguid != None:
                    tag += f"prototypeguid='{self.prototypeguid.XinActor.guid}' "
            if self.has_activationoffset: tag += f"activationoffset='{self.activationoffset}' "
            if self.has_activationheight: tag += f"activationheight='{self.activationheight}' "
            if self.has_activationrange: tag += f"activationrange='{self.activationrange}' "
            if self.has_activationangle: tag += f"activationangle='{self.activationangle}' "
            if self.has_assetcomponent: tag += f"assetcomponent='{self.assetcomponent}' "
            if self.has_transformseconds: tag += f"transformseconds='{self.transformseconds}' "
            if self.has_betweenseconds: tag += f"betweenseconds='{self.betweenseconds}' "
            if self.has_zapstart: tag += f"zapstart='{self.zapstart[0]},{self.zapstart[1]},{self.zapstart[2]}' "
            tag += "/>"
            return tag
    class OnOffSwitch(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_state: BoolProperty(name="State", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        state: EnumProperty(
            name="State", description="",
            items=[
                ("on","On","Generated default with script"),
                ("off","off","Generated from Real Data")
            ],
            default="on"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] On Off Switch")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_state")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_state: layout.prop(self, "state")

        def generate(self, obj):
            tag = f"<onoffswitch componentguid='{self.componentguid}' "
            if self.has_state: tag += f"state='{self.state}' "
            tag += "/>"
            return tag
    class AttachmentSpawner(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_actionradius: BoolProperty(name="Action Radius", description="",default=False)
        has_scale: BoolProperty(name="Scale", description="",default=False)
        has_attachmenttype: BoolProperty(name="Attachment Type", description="",default=True)
        has_power: BoolProperty(name="Power", description="",default=False)
        has_damage: BoolProperty(name="Damage", description="",default=True)
        has_firerate: BoolProperty(name="Fire Rate", description="",default=False)
        has_possessedfirerate: BoolProperty(name="Possessed Fire Rate", description="",default=False)
        has_clipsize: BoolProperty(name="Clip Size", description="",default=False)
        has_possessedclipsize: BoolProperty(name="Possessed Clip Size", description="",default=False)
        has_lethal: BoolProperty(name="Lethal", description="",default=True)
        has_beatdamage: BoolProperty(name="Beat Damage", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        actionradius: FloatProperty(
            name="Action Radius", description="",
            default=40
        )

        scale: FloatProperty(
            name="Scale", description="",
            default=1
        )

        attachmenttype: EnumProperty(
            name="Attachment Type", description="",
            items=[
                ("BrewGun","BrewGun","Generated default with script"),
                ("Saw","Saw","Generated from Real Data"),
                ("DrugGun","Drug Gun","Generated from Real Data"),
                ("SligGun","Slig Gun","Found in TagTemplate"),
                ("CrossBow","Cross Bow","Found in TagTemplate"),
                ("SligClub","Slig Club","Found in TagTemplate"),
                ("ShockRod","Shock Rod","Found in TagTemplate"),
                ("StandardShield","Standard Shield","Found in TagTemplate")
            ],
            default="BrewGun"
        )

        power: FloatProperty(
            name="Power", description="",
            default=1000
        )

        damage: FloatProperty(
            name="Damage", description="",
            default=10
        )

        firerate: IntProperty(
            name="Fire Rate", description="",
            default=10
        )

        possessedfirerate: IntProperty(
            name="Possessed Fire Rate", description="",
            default=10
        )

        clipsize: IntProperty(
            name="Clip Size", description="",
            default=40
        )

        possessedclipsize: IntProperty(
            name="Possessed Clip Size", description="",
            default=-1
        )

        lethal: BoolProperty(
            name="Lethal", description="",
            default=0
        )

        beatdamage: IntProperty(
            name="Beat Damage", description="",
            default=10
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Attachment Spawner")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_actionradius")
                box.prop(self, "has_scale")
                box.prop(self, "has_attachmenttype")
                box.prop(self, "has_power")
                box.prop(self, "has_damage")
                box.prop(self, "has_firerate")
                box.prop(self, "has_possessedfirerate")
                box.prop(self, "has_clipsize")
                box.prop(self, "has_possessedclipsize")
                box.prop(self, "has_lethal")
                box.prop(self, "has_beatdamage")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_actionradius: layout.prop(self, "actionradius")
            if self.has_scale: layout.prop(self, "scale")
            if self.has_attachmenttype: layout.prop(self, "attachmenttype")
            if self.has_power: layout.prop(self, "power")
            if self.has_damage: layout.prop(self, "damage")
            if self.has_firerate: layout.prop(self, "firerate")
            if self.has_possessedfirerate: layout.prop(self, "possessedfirerate")
            if self.has_clipsize: layout.prop(self, "clipsize")
            if self.has_possessedclipsize: layout.prop(self, "possessedclipsize")
            if self.has_lethal: layout.prop(self, "lethal")
            if self.has_beatdamage: layout.prop(self, "beatdamage")

        def generate(self, obj):
            tag = f"<attachmentspawner componentguid='{self.componentguid}' "
            if self.has_actionradius: tag += f"actionradius='{self.actionradius}' "
            if self.has_scale: tag += f"scale='{self.scale}' "
            if self.has_attachmenttype: tag += f"attachmenttype='{self.attachmenttype}' "
            if self.has_power: tag += f"power='{self.power}' "
            if self.has_damage: tag += f"damage='{self.damage}' "
            if self.has_firerate: tag += f"firerate='{self.firerate}' "
            if self.has_possessedfirerate: tag += f"possessedfirerate='{self.possessedfirerate}' "
            if self.has_clipsize: tag += f"clipsize='{self.clipsize}' "
            if self.has_possessedclipsize: tag += f"possessedclipsize='{self.possessedclipsize}' "
            if self.has_lethal: tag += f"lethal='{self.lethal}' "
            if self.has_beatdamage: tag += f"beatdamage='{self.beatdamage}' "
            tag += "/>"
            return tag
    class Floatation(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_exploding: BoolProperty(name="Exploding", description="",default=True)
        has_sinkdepth: BoolProperty(name="Skin Depth", description="",default=False)
        has_immovable: BoolProperty(name="Immovable", description="",default=False)
        has_checkoffset: BoolProperty(name="Check Offset", description="",default=False)
        has_bobspeed: BoolProperty(name="Bob Speed", description="",default=False)
        has_bobamplitude: BoolProperty(name="Bob Amplitude", description="",default=False)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        exploding: BoolProperty(
            name="Exploding", description="",
            default=False
        )

        sinkdepth: FloatProperty(
            name="Skin Depth", description="",
            default=6
        )

        immovable: BoolProperty(
            name="Immovable", description="",
            default=False
        )

        checkoffset: FloatProperty(
            name="Check Offset", description="",
            default=-8.35
        )

        bobspeed: FloatProperty(
            name="Bob Speed", description="",
            default=1.2
        )

        bobamplitude: FloatProperty(
            name="Bob Amplitude", description="",
            default=2.0
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Floatation")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_exploding")
                box.prop(self, "has_sinkdepth")
                box.prop(self, "has_immovable")
                box.prop(self, "has_checkoffset")
                box.prop(self, "has_bobspeed")
                box.prop(self, "has_bobamplitude")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_exploding: layout.prop(self, "exploding")
            if self.has_sinkdepth: layout.prop(self, "sinkdepth")
            if self.has_immovable: layout.prop(self, "immovable")
            if self.has_checkoffset: layout.prop(self, "checkoffset")
            if self.has_bobspeed: layout.prop(self, "bobspeed")
            if self.has_bobamplitude: layout.prop(self, "bobamplitude")

        def generate(self, obj):
            tag = f"<floatation componentguid='{self.componentguid}' "
            if self.has_exploding: tag += f"exploding='{self.exploding}' "
            if self.has_sinkdepth: tag += f"sinkdepth='{self.sinkdepth}' "
            if self.has_immovable: tag += f"immovable='{self.immovable}' "
            if self.has_checkoffset: tag += f"checkoffset='{self.checkoffset}' "
            if self.has_bobspeed: tag += f"bobspeed='{self.bobspeed}' "
            if self.has_bobamplitude: tag += f"bobamplitude='{self.bobamplitude}' "
            tag += f"rotation='{genRot([obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z])}' "
            tag += "/>"
            return tag
    class ActorTally(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_alivedisplayid: BoolProperty(name="Alive Display Id", description="",default=True)
        has_killeddisplayid: BoolProperty(name="Killed Display Id", description="",default=True)
        has_rescueddisplayid: BoolProperty(name="Rescued Display Id", description="",default=True)
        has_talliedflavors: BoolProperty(name="Tallied Flavors", description="",default=True)
        has_updateinterval: BoolProperty(name="Update Interval", description="",default=False)
        has_useglobaltally: BoolProperty(name="Use Global Tally", description="",default=False)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        alivedisplayid: IntProperty(
            name="Alive Display Id", description="",
            default=0
        )

        killeddisplayid: IntProperty(
            name="Killed Display Id", description="",
            default=0
        )

        rescueddisplayid: IntProperty(
            name="Rescued Display Id", description="",
            default=0
        )

        talliedflavors: StringProperty(
            name="Tallied Flavors", description="",
            default=""
        )

        updateinterval: FloatProperty(
            name="Update Interval", description="",
            default=0.5
        )

        useglobaltally: BoolProperty(
            name="Use Global Tally", description="",
            default=False
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Actor Tally")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_alivedisplayid")
                box.prop(self, "has_killeddisplayid")
                box.prop(self, "has_rescueddisplayid")
                box.prop(self, "has_talliedflavors")
                box.prop(self, "has_updateinterval")
                box.prop(self, "has_useglobaltally")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_alivedisplayid: layout.prop(self, "alivedisplayid")
            if self.has_killeddisplayid: layout.prop(self, "killeddisplayid")
            if self.has_rescueddisplayid: layout.prop(self, "rescueddisplayid")
            if self.has_talliedflavors: layout.prop(self, "talliedflavors")
            if self.has_updateinterval: layout.prop(self, "updateinterval")
            if self.has_useglobaltally: layout.prop(self, "useglobaltally")

        def generate(self, obj):
            tag = f"<actortally componentguid='{self.componentguid}' "
            if self.has_alivedisplayid: tag += f"alivedisplayid='{self.alivedisplayid}' "
            if self.has_killeddisplayid: tag += f"killeddisplayid='{self.killeddisplayid}' "
            if self.has_rescueddisplayid: tag += f"rescueddisplayid='{self.rescueddisplayid}' "
            if self.has_talliedflavors: tag += f"talliedflavors='{self.talliedflavors}' "
            if self.has_updateinterval: tag += f"updateinterval='{self.updateinterval}' "
            if self.has_useglobaltally: tag += f"useglobaltally='{self.useglobaltally}' "
            tag += "/>"
            return tag
    class ActorTally2(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_alivedisplayid: BoolProperty(name="Alive Display Id", description="",default=True)
        has_killeddisplayid: BoolProperty(name="Killed Display Id", description="",default=True)
        has_rescueddisplayid: BoolProperty(name="Rescued Display Id", description="",default=True)
        has_talliedflavors: BoolProperty(name="Tallied Flavors", description="",default=True)
        has_updateinterval: BoolProperty(name="Update Interval", description="",default=False)
        has_useglobaltally: BoolProperty(name="Use Global Tally", description="",default=False)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        alivedisplayid: IntProperty(
            name="Alive Display Id", description="",
            default=0
        )

        killeddisplayid: IntProperty(
            name="Killed Display Id", description="",
            default=0
        )

        rescueddisplayid: IntProperty(
            name="Rescued Display Id", description="",
            default=0
        )

        talliedflavors: StringProperty(
            name="Tallied Flavors", description="",
            default=""
        )

        updateinterval: FloatProperty(
            name="Update Interval", description="",
            default=0.5
        )

        useglobaltally: BoolProperty(
            name="Use Global Tally", description="",
            default=False
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Actor Tally 2")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_alivedisplayid")
                box.prop(self, "has_killeddisplayid")
                box.prop(self, "has_rescueddisplayid")
                box.prop(self, "has_talliedflavors")
                box.prop(self, "has_updateinterval")
                box.prop(self, "has_useglobaltally")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_alivedisplayid: layout.prop(self, "alivedisplayid")
            if self.has_killeddisplayid: layout.prop(self, "killeddisplayid")
            if self.has_rescueddisplayid: layout.prop(self, "rescueddisplayid")
            if self.has_talliedflavors: layout.prop(self, "talliedflavors")
            if self.has_updateinterval: layout.prop(self, "updateinterval")
            if self.has_useglobaltally: layout.prop(self, "useglobaltally")

        def generate(self, obj):
            tag = f"<actortally2 componentguid='{self.componentguid}' "
            if self.has_alivedisplayid: tag += f"alivedisplayid='{self.alivedisplayid}' "
            if self.has_killeddisplayid: tag += f"killeddisplayid='{self.killeddisplayid}' "
            if self.has_rescueddisplayid: tag += f"rescueddisplayid='{self.rescueddisplayid}' "
            if self.has_talliedflavors: tag += f"talliedflavors='{self.talliedflavors}' "
            if self.has_updateinterval: tag += f"updateinterval='{self.updateinterval}' "
            if self.has_useglobaltally: tag += f"useglobaltally='{self.useglobaltally}' "
            tag += "/>"
            return tag
    class ActorTally3(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_alivedisplayid: BoolProperty(name="Alive Display Id", description="",default=True)
        has_killeddisplayid: BoolProperty(name="Killed Display Id", description="",default=True)
        has_rescueddisplayid: BoolProperty(name="Rescued Display Id", description="",default=True)
        has_talliedflavors: BoolProperty(name="Tallied Flavors", description="",default=True)
        has_updateinterval: BoolProperty(name="Update Interval", description="",default=False)
        has_useglobaltally: BoolProperty(name="Use Global Tally", description="",default=False)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        alivedisplayid: IntProperty(
            name="Alive Display Id", description="",
            default=0
        )

        killeddisplayid: IntProperty(
            name="Killed Display Id", description="",
            default=0
        )

        rescueddisplayid: IntProperty(
            name="Rescued Display Id", description="",
            default=0
        )

        talliedflavors: StringProperty(
            name="Tallied Flavors", description="",
            default=""
        )

        updateinterval: FloatProperty(
            name="Update Interval", description="",
            default=0.5
        )

        useglobaltally: BoolProperty(
            name="Use Global Tally", description="",
            default=False
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Actor Tally 3")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_alivedisplayid")
                box.prop(self, "has_killeddisplayid")
                box.prop(self, "has_rescueddisplayid")
                box.prop(self, "has_talliedflavors")
                box.prop(self, "has_updateinterval")
                box.prop(self, "has_useglobaltally")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_alivedisplayid: layout.prop(self, "alivedisplayid")
            if self.has_killeddisplayid: layout.prop(self, "killeddisplayid")
            if self.has_rescueddisplayid: layout.prop(self, "rescueddisplayid")
            if self.has_talliedflavors: layout.prop(self, "talliedflavors")
            if self.has_updateinterval: layout.prop(self, "updateinterval")
            if self.has_useglobaltally: layout.prop(self, "useglobaltally")

        def generate(self, obj):
            tag = f"<actortally3 componentguid='{self.componentguid}' "
            if self.has_alivedisplayid: tag += f"alivedisplayid='{self.alivedisplayid}' "
            if self.has_killeddisplayid: tag += f"killeddisplayid='{self.killeddisplayid}' "
            if self.has_rescueddisplayid: tag += f"rescueddisplayid='{self.rescueddisplayid}' "
            if self.has_talliedflavors: tag += f"talliedflavors='{self.talliedflavors}' "
            if self.has_updateinterval: tag += f"updateinterval='{self.updateinterval}' "
            if self.has_useglobaltally: tag += f"useglobaltally='{self.useglobaltally}' "
            tag += "/>"
            return tag
    class ActorTally4(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_alivedisplayid: BoolProperty(name="Alive Display Id", description="",default=True)
        has_killeddisplayid: BoolProperty(name="Killed Display Id", description="",default=True)
        has_rescueddisplayid: BoolProperty(name="Rescued Display Id", description="",default=True)
        has_talliedflavors: BoolProperty(name="Tallied Flavors", description="",default=True)
        has_updateinterval: BoolProperty(name="Update Interval", description="",default=False)
        has_useglobaltally: BoolProperty(name="Use Global Tally", description="",default=False)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        alivedisplayid: IntProperty(
            name="Alive Display Id", description="",
            default=0
        )

        killeddisplayid: IntProperty(
            name="Killed Display Id", description="",
            default=0
        )

        rescueddisplayid: IntProperty(
            name="Rescued Display Id", description="",
            default=0
        )

        talliedflavors: StringProperty(
            name="Tallied Flavors", description="",
            default=""
        )

        updateinterval: FloatProperty(
            name="Update Interval", description="",
            default=0.5
        )

        useglobaltally: BoolProperty(
            name="Use Global Tally", description="",
            default=False
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Actor Tally 4")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_alivedisplayid")
                box.prop(self, "has_killeddisplayid")
                box.prop(self, "has_rescueddisplayid")
                box.prop(self, "has_talliedflavors")
                box.prop(self, "has_updateinterval")
                box.prop(self, "has_useglobaltally")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_alivedisplayid: layout.prop(self, "alivedisplayid")
            if self.has_killeddisplayid: layout.prop(self, "killeddisplayid")
            if self.has_rescueddisplayid: layout.prop(self, "rescueddisplayid")
            if self.has_talliedflavors: layout.prop(self, "talliedflavors")
            if self.has_updateinterval: layout.prop(self, "updateinterval")
            if self.has_useglobaltally: layout.prop(self, "useglobaltally")

        def generate(self, obj):
            tag = f"<actortally4 componentguid='{self.componentguid}' "
            if self.has_alivedisplayid: tag += f"alivedisplayid='{self.alivedisplayid}' "
            if self.has_killeddisplayid: tag += f"killeddisplayid='{self.killeddisplayid}' "
            if self.has_rescueddisplayid: tag += f"rescueddisplayid='{self.rescueddisplayid}' "
            if self.has_talliedflavors: tag += f"talliedflavors='{self.talliedflavors}' "
            if self.has_updateinterval: tag += f"updateinterval='{self.updateinterval}' "
            if self.has_useglobaltally: tag += f"useglobaltally='{self.useglobaltally}' "
            tag += "/>"
            return tag
    class ActorTally5(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_alivedisplayid: BoolProperty(name="Alive Display Id", description="",default=True)
        has_killeddisplayid: BoolProperty(name="Killed Display Id", description="",default=True)
        has_rescueddisplayid: BoolProperty(name="Rescued Display Id", description="",default=True)
        has_talliedflavors: BoolProperty(name="Tallied Flavors", description="",default=True)
        has_updateinterval: BoolProperty(name="Update Interval", description="",default=False)
        has_useglobaltally: BoolProperty(name="Use Global Tally", description="",default=False)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        alivedisplayid: IntProperty(
            name="Alive Display Id", description="",
            default=0
        )

        killeddisplayid: IntProperty(
            name="Killed Display Id", description="",
            default=0
        )

        rescueddisplayid: IntProperty(
            name="Rescued Display Id", description="",
            default=0
        )

        talliedflavors: StringProperty(
            name="Tallied Flavors", description="",
            default=""
        )

        updateinterval: FloatProperty(
            name="Update Interval", description="",
            default=0.5
        )

        useglobaltally: BoolProperty(
            name="Use Global Tally", description="",
            default=False
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Actor Tally 5")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_alivedisplayid")
                box.prop(self, "has_killeddisplayid")
                box.prop(self, "has_rescueddisplayid")
                box.prop(self, "has_talliedflavors")
                box.prop(self, "has_updateinterval")
                box.prop(self, "has_useglobaltally")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_alivedisplayid: layout.prop(self, "alivedisplayid")
            if self.has_killeddisplayid: layout.prop(self, "killeddisplayid")
            if self.has_rescueddisplayid: layout.prop(self, "rescueddisplayid")
            if self.has_talliedflavors: layout.prop(self, "talliedflavors")
            if self.has_updateinterval: layout.prop(self, "updateinterval")
            if self.has_useglobaltally: layout.prop(self, "useglobaltally")

        def generate(self, obj):
            tag = f"<actortally5 componentguid='{self.componentguid}' "
            if self.has_alivedisplayid: tag += f"alivedisplayid='{self.alivedisplayid}' "
            if self.has_killeddisplayid: tag += f"killeddisplayid='{self.killeddisplayid}' "
            if self.has_rescueddisplayid: tag += f"rescueddisplayid='{self.rescueddisplayid}' "
            if self.has_talliedflavors: tag += f"talliedflavors='{self.talliedflavors}' "
            if self.has_updateinterval: tag += f"updateinterval='{self.updateinterval}' "
            if self.has_useglobaltally: tag += f"useglobaltally='{self.useglobaltally}' "
            tag += "/>"
            return tag
    class TextDisplay(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_offset: BoolProperty(name="Offset", description="",default=True)
        has_color: BoolProperty(name="Color", description="",default=True)
        has_text: BoolProperty(name="Text", description="",default=True)
        has_font: BoolProperty(name="Font", description="",default=True)
        has_displaytype: BoolProperty(name="Display Type", description="",default=True)
        has_alignment: BoolProperty(name="Alignment", description="",default=True)
        has_kern: BoolProperty(name="Kern", description="",default=False)
        has_speed: BoolProperty(name="Speed", description="",default=True)
        has_size: BoolProperty(name="Size", description="",default=True)
        has_alpha: BoolProperty(name="Alpha", description="",default=True)
        has_fadeintime: BoolProperty(name="Fade In Time", description="",default=True)
        has_fadeouttime: BoolProperty(name="Fade Out Time", description="",default=True)
        has_width: BoolProperty(name="Width", description="",default=True)
        has_height: BoolProperty(name="Height", description="",default=True)
        has_widthscale: BoolProperty(name="Width Scale", description="",default=False)
        has_id: BoolProperty(name="Id", description="",default=True)
        has_active: BoolProperty(name="Active", description="",default=True)
        has_node: BoolProperty(name="Node", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        id: EnumProperty(
            name="Id", description="",
            items=[
                ("","","Found in Tag Template"),
                ("spooce","spooce","Generated from Real Data"),
                ("display","display","Generated from Real Data")
            ]
        )

        active: BoolProperty(
            name="Active", description="",
            default=True
        )

        width: FloatProperty(
            name="Width", description="",
            default=72
        )

        height: FloatProperty(
            name="Height", description="",
            default=15
        )

        text: StringProperty(
            name="Text", description="",
            default=""
        )

        font: EnumProperty(
            name="Font", description="",
            items=[
    
                ("Main","Main","Generated default with script"),
                ("LED","LED","Generated from Real Data"),
                ("native","Native","Generated from Real Data"),
                ("inventory","Inventory","Found in TagTemplate"),
                ("newled","New LED","Found in TagTemplate"),
                
            ],
            default="Main"
        )

        size: FloatProperty(
            name="Size", description="",
            default=5
        )

        widthscale: FloatProperty(
            name="Width Scale", description="",
            default=1
        )

        kern: FloatProperty(
            name="Kern", description="",
            default=-1
        )

        speed: FloatProperty(
            name="Speed", description="",
            default=0
        )

        color: FloatVectorProperty(
            name="Color", description="",
            subtype="COLOR",
            min=0, max=1,
            default=(1,1,1)
        )

        alpha: FloatProperty(
            name="Alpha", description="",
            default=1
        )

        node: StringProperty(
            name="Node", description="",
            default="none"
        )

        offset: FloatVectorProperty(
            name="Offset", description="",
            subtype="XYZ",
            default=(0,0,0)
        )

        fadeintime: FloatProperty(
            name="Fade In Time", description="",
            default=0.4
        )

        fadeouttime: FloatProperty(
            name="Fade Out Time", description="",
            default=0.8
        )

        displaytype: EnumProperty(
            name="Display Type", description="",
            items=[
                ("scrolling","scrolling","Generated default with script"),
                ("floating","Floating","Generated from Real Data"),
                ("static","Static","Generated from Real Data"),
                ("rising","Rising","Generated from Real Data")
            ],
            default="scrolling"
        )

        alignment: EnumProperty(
            name="Alignment", description="",
            items=[
                ("left","left","Generated default with script"),
                ("center","Center","Generated from Real Data"),
                ("right","Right","Found in TagTemplate"),
            ],
            default="left"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Text Display")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_offset")
                box.prop(self, "has_color")
                box.prop(self, "has_text")
                box.prop(self, "has_font")
                box.prop(self, "has_displaytype")
                box.prop(self, "has_alignment")
                box.prop(self, "has_kern")
                box.prop(self, "has_speed")
                box.prop(self, "has_size")
                box.prop(self, "has_alpha")
                box.prop(self, "has_fadeintime")
                box.prop(self, "has_fadeouttime")
                box.prop(self, "has_width")
                box.prop(self, "has_height")
                box.prop(self, "has_widthscale")
                box.prop(self, "has_id")
                box.prop(self, "has_active")
                box.prop(self, "has_node")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_offset: layout.prop(self, "offset")
            if self.has_color: layout.prop(self, "color")
            if self.has_text: layout.prop(self, "text")
            if self.has_font: layout.prop(self, "font")
            if self.has_displaytype: layout.prop(self, "displaytype")
            if self.has_alignment: layout.prop(self, "alignment")
            if self.has_kern: layout.prop(self, "kern")
            if self.has_speed: layout.prop(self, "speed")
            if self.has_size: layout.prop(self, "size")
            if self.has_alpha: layout.prop(self, "alpha")
            if self.has_fadeintime: layout.prop(self, "fadeintime")
            if self.has_fadeouttime: layout.prop(self, "fadeouttime")
            if self.has_width: layout.prop(self, "width")
            if self.has_height: layout.prop(self, "height")
            if self.has_widthscale: layout.prop(self, "widthscale")
            if self.has_id: layout.prop(self, "id")
            if self.has_active: layout.prop(self, "active")
            if self.has_node: layout.prop(self, "node")

        def generate(self, obj):
            tag = f"<textdisplay componentguid='{self.componentguid}' "
            if self.has_id: tag += f"id='{self.id}' "
            if self.has_active: tag += f"active='{self.active}' "
            if self.has_width: tag += f"width='{self.width}' "
            if self.has_height: tag += f"height='{self.height}' "
            if self.has_text: tag += f"text='{self.text}' "
            if self.has_font: tag += f"font='{self.font}' "
            if self.has_size: tag += f"size='{self.size}' "
            if self.has_widthscale: tag += f"widthscale='{self.widthscale}' "
            if self.has_kern: tag += f"kern='{self.kern}' "
            if self.has_speed: tag += f"speed='{self.speed}' "
            if self.has_color: tag += f"color='{self.color[0]},{self.color[1]},{self.color[2]}' "
            if self.has_alpha: tag += f"alpha='{self.alpha}' "
            if self.has_node: tag += f"node='{self.node}' "
            if self.has_offset: tag += f"offset='{self.offset[0]},{self.offset[1]},{self.offset[2]}' "
            if self.has_fadeintime: tag += f"fadeintime='{self.fadeintime}' "
            if self.has_fadeouttime: tag += f"fadeouttime='{self.fadeouttime}' "
            if self.has_displaytype: tag += f"displaytype='{self.displaytype}' "
            if self.has_alignment: tag += f"alignment='{self.alignment}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class TextDisplay2(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_offset: BoolProperty(name="Offset", description="",default=True)
        has_color: BoolProperty(name="Color", description="",default=True)
        has_text: BoolProperty(name="Text", description="",default=True)
        has_font: BoolProperty(name="Font", description="",default=True)
        has_displaytype: BoolProperty(name="Display Type", description="",default=True)
        has_alignment: BoolProperty(name="Alignment", description="",default=True)
        has_kern: BoolProperty(name="Kern", description="",default=False)
        has_speed: BoolProperty(name="Speed", description="",default=True)
        has_size: BoolProperty(name="Size", description="",default=True)
        has_alpha: BoolProperty(name="Alpha", description="",default=True)
        has_fadeintime: BoolProperty(name="Fade In Time", description="",default=True)
        has_fadeouttime: BoolProperty(name="Fade Out Time", description="",default=True)
        has_width: BoolProperty(name="Width", description="",default=True)
        has_height: BoolProperty(name="Height", description="",default=True)
        has_widthscale: BoolProperty(name="Width Scale", description="",default=False)
        has_id: BoolProperty(name="Id", description="",default=True)
        has_active: BoolProperty(name="Active", description="",default=True)
        has_node: BoolProperty(name="Node", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        id: EnumProperty(
            name="Id", description="",
            items=[
                ("","","Found in Tag Template"),
                ("spooce","spooce","Generated from Real Data"),
                ("display","display","Generated from Real Data")
            ]
        )

        active: BoolProperty(
            name="Active", description="",
            default=True
        )

        width: FloatProperty(
            name="Width", description="",
            default=72
        )

        height: FloatProperty(
            name="Height", description="",
            default=15
        )

        text: StringProperty(
            name="Text", description="",
            default=""
        )

        font: EnumProperty(
            name="Font", description="",
            items=[
    
                ("Main","Main","Generated default with script"),
                ("LED","LED","Generated from Real Data"),
                ("native","Native","Generated from Real Data"),
                ("inventory","Inventory","Found in TagTemplate"),
                ("newled","New LED","Found in TagTemplate"),
                
            ],
            default="Main"
        )

        size: FloatProperty(
            name="Size", description="",
            default=5
        )

        widthscale: FloatProperty(
            name="Width Scale", description="",
            default=1
        )

        kern: FloatProperty(
            name="Kern", description="",
            default=-1
        )

        speed: FloatProperty(
            name="Speed", description="",
            default=0
        )

        color: FloatVectorProperty(
            name="Color", description="",
            subtype="COLOR",
            min=0, max=1,
            default=(1,1,1)
        )

        alpha: FloatProperty(
            name="Alpha", description="",
            default=1
        )

        node: StringProperty(
            name="Node", description="",
            default="none"
        )

        offset: FloatVectorProperty(
            name="Offset", description="",
            subtype="XYZ",
            default=(0,0,0)
        )

        fadeintime: FloatProperty(
            name="Fade In Time", description="",
            default=0.4
        )

        fadeouttime: FloatProperty(
            name="Fade Out Time", description="",
            default=0.8
        )

        displaytype: EnumProperty(
            name="Display Type", description="",
            items=[
                ("scrolling","scrolling","Generated default with script"),
                ("floating","Floating","Generated from Real Data"),
                ("static","Static","Generated from Real Data"),
                ("rising","Rising","Generated from Real Data")
            ],
            default="scrolling"
        )

        alignment: EnumProperty(
            name="Alignment", description="",
            items=[
                ("left","left","Generated default with script"),
                ("center","Center","Generated from Real Data"),
                ("right","Right","Found in TagTemplate"),
            ],
            default="left"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Text Display 2")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_offset")
                box.prop(self, "has_color")
                box.prop(self, "has_text")
                box.prop(self, "has_font")
                box.prop(self, "has_displaytype")
                box.prop(self, "has_alignment")
                box.prop(self, "has_kern")
                box.prop(self, "has_speed")
                box.prop(self, "has_size")
                box.prop(self, "has_alpha")
                box.prop(self, "has_fadeintime")
                box.prop(self, "has_fadeouttime")
                box.prop(self, "has_width")
                box.prop(self, "has_height")
                box.prop(self, "has_widthscale")
                box.prop(self, "has_id")
                box.prop(self, "has_active")
                box.prop(self, "has_node")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_offset: layout.prop(self, "offset")
            if self.has_color: layout.prop(self, "color")
            if self.has_text: layout.prop(self, "text")
            if self.has_font: layout.prop(self, "font")
            if self.has_displaytype: layout.prop(self, "displaytype")
            if self.has_alignment: layout.prop(self, "alignment")
            if self.has_kern: layout.prop(self, "kern")
            if self.has_speed: layout.prop(self, "speed")
            if self.has_size: layout.prop(self, "size")
            if self.has_alpha: layout.prop(self, "alpha")
            if self.has_fadeintime: layout.prop(self, "fadeintime")
            if self.has_fadeouttime: layout.prop(self, "fadeouttime")
            if self.has_width: layout.prop(self, "width")
            if self.has_height: layout.prop(self, "height")
            if self.has_widthscale: layout.prop(self, "widthscale")
            if self.has_id: layout.prop(self, "id")
            if self.has_active: layout.prop(self, "active")
            if self.has_node: layout.prop(self, "node")

        def generate(self, obj):
            tag = f"<textdisplay2 componentguid='{self.componentguid}' "
            if self.has_id: tag += f"id='{self.id}' "
            if self.has_active: tag += f"active='{self.active}' "
            if self.has_width: tag += f"width='{self.width}' "
            if self.has_height: tag += f"height='{self.height}' "
            if self.has_text: tag += f"text='{self.text}' "
            if self.has_font: tag += f"font='{self.font}' "
            if self.has_size: tag += f"size='{self.size}' "
            if self.has_widthscale: tag += f"widthscale='{self.widthscale}' "
            if self.has_kern: tag += f"kern='{self.kern}' "
            if self.has_speed: tag += f"speed='{self.speed}' "
            if self.has_color: tag += f"color='{self.color[0]},{self.color[1]},{self.color[2]}' "
            if self.has_alpha: tag += f"alpha='{self.alpha}' "
            if self.has_node: tag += f"node='{self.node}' "
            if self.has_offset: tag += f"offset='{self.offset[0]},{self.offset[1]},{self.offset[2]}' "
            if self.has_fadeintime: tag += f"fadeintime='{self.fadeintime}' "
            if self.has_fadeouttime: tag += f"fadeouttime='{self.fadeouttime}' "
            if self.has_displaytype: tag += f"displaytype='{self.displaytype}' "
            if self.has_alignment: tag += f"alignment='{self.alignment}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class TextDisplay3(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_offset: BoolProperty(name="Offset", description="",default=True)
        has_color: BoolProperty(name="Color", description="",default=True)
        has_text: BoolProperty(name="Text", description="",default=True)
        has_font: BoolProperty(name="Font", description="",default=True)
        has_displaytype: BoolProperty(name="Display Type", description="",default=True)
        has_alignment: BoolProperty(name="Alignment", description="",default=True)
        has_kern: BoolProperty(name="Kern", description="",default=False)
        has_speed: BoolProperty(name="Speed", description="",default=True)
        has_size: BoolProperty(name="Size", description="",default=True)
        has_alpha: BoolProperty(name="Alpha", description="",default=True)
        has_fadeintime: BoolProperty(name="Fade In Time", description="",default=True)
        has_fadeouttime: BoolProperty(name="Fade Out Time", description="",default=True)
        has_width: BoolProperty(name="Width", description="",default=True)
        has_height: BoolProperty(name="Height", description="",default=True)
        has_widthscale: BoolProperty(name="Width Scale", description="",default=False)
        has_id: BoolProperty(name="Id", description="",default=True)
        has_active: BoolProperty(name="Active", description="",default=True)
        has_node: BoolProperty(name="Node", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        id: EnumProperty(
            name="Id", description="",
            items=[
                ("","","Found in Tag Template"),
                ("spooce","spooce","Generated from Real Data"),
                ("display","display","Generated from Real Data")
            ]
        )

        active: BoolProperty(
            name="Active", description="",
            default=True
        )

        width: FloatProperty(
            name="Width", description="",
            default=72
        )

        height: FloatProperty(
            name="Height", description="",
            default=15
        )

        text: StringProperty(
            name="Text", description="",
            default=""
        )

        font: EnumProperty(
            name="Font", description="",
            items=[
    
                ("Main","Main","Generated default with script"),
                ("LED","LED","Generated from Real Data"),
                ("native","Native","Generated from Real Data"),
                ("inventory","Inventory","Found in TagTemplate"),
                ("newled","New LED","Found in TagTemplate"),
                
            ],
            default="Main"
        )

        size: FloatProperty(
            name="Size", description="",
            default=5
        )

        widthscale: FloatProperty(
            name="Width Scale", description="",
            default=1
        )

        kern: FloatProperty(
            name="Kern", description="",
            default=-1
        )

        speed: FloatProperty(
            name="Speed", description="",
            default=0
        )

        color: FloatVectorProperty(
            name="Color", description="",
            subtype="COLOR",
            min=0, max=1,
            default=(1,1,1)
        )

        alpha: FloatProperty(
            name="Alpha", description="",
            default=1
        )

        node: StringProperty(
            name="Node", description="",
            default="none"
        )

        offset: FloatVectorProperty(
            name="Offset", description="",
            subtype="XYZ",
            default=(0,0,0)
        )

        fadeintime: FloatProperty(
            name="Fade In Time", description="",
            default=0.4
        )

        fadeouttime: FloatProperty(
            name="Fade Out Time", description="",
            default=0.8
        )

        displaytype: EnumProperty(
            name="Display Type", description="",
            items=[
                ("scrolling","scrolling","Generated default with script"),
                ("floating","Floating","Generated from Real Data"),
                ("static","Static","Generated from Real Data"),
                ("rising","Rising","Generated from Real Data")
            ],
            default="scrolling"
        )

        alignment: EnumProperty(
            name="Alignment", description="",
            items=[
                ("left","left","Generated default with script"),
                ("center","Center","Generated from Real Data"),
                ("right","Right","Found in TagTemplate"),
            ],
            default="left"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Text Display 3")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_offset")
                box.prop(self, "has_color")
                box.prop(self, "has_text")
                box.prop(self, "has_font")
                box.prop(self, "has_displaytype")
                box.prop(self, "has_alignment")
                box.prop(self, "has_kern")
                box.prop(self, "has_speed")
                box.prop(self, "has_size")
                box.prop(self, "has_alpha")
                box.prop(self, "has_fadeintime")
                box.prop(self, "has_fadeouttime")
                box.prop(self, "has_width")
                box.prop(self, "has_height")
                box.prop(self, "has_widthscale")
                box.prop(self, "has_id")
                box.prop(self, "has_active")
                box.prop(self, "has_node")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_offset: layout.prop(self, "offset")
            if self.has_color: layout.prop(self, "color")
            if self.has_text: layout.prop(self, "text")
            if self.has_font: layout.prop(self, "font")
            if self.has_displaytype: layout.prop(self, "displaytype")
            if self.has_alignment: layout.prop(self, "alignment")
            if self.has_kern: layout.prop(self, "kern")
            if self.has_speed: layout.prop(self, "speed")
            if self.has_size: layout.prop(self, "size")
            if self.has_alpha: layout.prop(self, "alpha")
            if self.has_fadeintime: layout.prop(self, "fadeintime")
            if self.has_fadeouttime: layout.prop(self, "fadeouttime")
            if self.has_width: layout.prop(self, "width")
            if self.has_height: layout.prop(self, "height")
            if self.has_widthscale: layout.prop(self, "widthscale")
            if self.has_id: layout.prop(self, "id")
            if self.has_active: layout.prop(self, "active")
            if self.has_node: layout.prop(self, "node")

        def generate(self, obj):
            tag = f"<textdisplay3 componentguid='{self.componentguid}' "
            if self.has_id: tag += f"id='{self.id}' "
            if self.has_active: tag += f"active='{self.active}' "
            if self.has_width: tag += f"width='{self.width}' "
            if self.has_height: tag += f"height='{self.height}' "
            if self.has_text: tag += f"text='{self.text}' "
            if self.has_font: tag += f"font='{self.font}' "
            if self.has_size: tag += f"size='{self.size}' "
            if self.has_widthscale: tag += f"widthscale='{self.widthscale}' "
            if self.has_kern: tag += f"kern='{self.kern}' "
            if self.has_speed: tag += f"speed='{self.speed}' "
            if self.has_color: tag += f"color='{self.color[0]},{self.color[1]},{self.color[2]}' "
            if self.has_alpha: tag += f"alpha='{self.alpha}' "
            if self.has_node: tag += f"node='{self.node}' "
            if self.has_offset: tag += f"offset='{self.offset[0]},{self.offset[1]},{self.offset[2]}' "
            if self.has_fadeintime: tag += f"fadeintime='{self.fadeintime}' "
            if self.has_fadeouttime: tag += f"fadeouttime='{self.fadeouttime}' "
            if self.has_displaytype: tag += f"displaytype='{self.displaytype}' "
            if self.has_alignment: tag += f"alignment='{self.alignment}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class TextDisplay4(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_offset: BoolProperty(name="Offset", description="",default=True)
        has_color: BoolProperty(name="Color", description="",default=True)
        has_text: BoolProperty(name="Text", description="",default=True)
        has_font: BoolProperty(name="Font", description="",default=True)
        has_displaytype: BoolProperty(name="Display Type", description="",default=True)
        has_alignment: BoolProperty(name="Alignment", description="",default=True)
        has_kern: BoolProperty(name="Kern", description="",default=False)
        has_speed: BoolProperty(name="Speed", description="",default=True)
        has_size: BoolProperty(name="Size", description="",default=True)
        has_alpha: BoolProperty(name="Alpha", description="",default=True)
        has_fadeintime: BoolProperty(name="Fade In Time", description="",default=True)
        has_fadeouttime: BoolProperty(name="Fade Out Time", description="",default=True)
        has_width: BoolProperty(name="Width", description="",default=True)
        has_height: BoolProperty(name="Height", description="",default=True)
        has_widthscale: BoolProperty(name="Width Scale", description="",default=False)
        has_id: BoolProperty(name="Id", description="",default=True)
        has_active: BoolProperty(name="Active", description="",default=True)
        has_node: BoolProperty(name="Node", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        id: EnumProperty(
            name="Id", description="",
            items=[
                ("","","Found in Tag Template"),
                ("spooce","spooce","Generated from Real Data"),
                ("display","display","Generated from Real Data")
            ]
        )

        active: BoolProperty(
            name="Active", description="",
            default=True
        )

        width: FloatProperty(
            name="Width", description="",
            default=72
        )

        height: FloatProperty(
            name="Height", description="",
            default=15
        )

        text: StringProperty(
            name="Text", description="",
            default=""
        )

        font: EnumProperty(
            name="Font", description="",
            items=[
    
                ("Main","Main","Generated default with script"),
                ("LED","LED","Generated from Real Data"),
                ("native","Native","Generated from Real Data"),
                ("inventory","Inventory","Found in TagTemplate"),
                ("newled","New LED","Found in TagTemplate"),
                
            ],
            default="Main"
        )

        size: FloatProperty(
            name="Size", description="",
            default=5
        )

        widthscale: FloatProperty(
            name="Width Scale", description="",
            default=1
        )

        kern: FloatProperty(
            name="Kern", description="",
            default=-1
        )

        speed: FloatProperty(
            name="Speed", description="",
            default=0
        )

        color: FloatVectorProperty(
            name="Color", description="",
            subtype="COLOR",
            min=0, max=1,
            default=(1,1,1)
        )

        alpha: FloatProperty(
            name="Alpha", description="",
            default=1
        )

        node: StringProperty(
            name="Node", description="",
            default="none"
        )

        offset: FloatVectorProperty(
            name="Offset", description="",
            subtype="XYZ",
            default=(0,0,0)
        )

        fadeintime: FloatProperty(
            name="Fade In Time", description="",
            default=0.4
        )

        fadeouttime: FloatProperty(
            name="Fade Out Time", description="",
            default=0.8
        )

        displaytype: EnumProperty(
            name="Display Type", description="",
            items=[
                ("scrolling","scrolling","Generated default with script"),
                ("floating","Floating","Generated from Real Data"),
                ("static","Static","Generated from Real Data"),
                ("rising","Rising","Generated from Real Data")
            ],
            default="scrolling"
        )

        alignment: EnumProperty(
            name="Alignment", description="",
            items=[
                ("left","left","Generated default with script"),
                ("center","Center","Generated from Real Data"),
                ("right","Right","Found in TagTemplate"),
            ],
            default="left"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Text Display 4")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_offset")
                box.prop(self, "has_color")
                box.prop(self, "has_text")
                box.prop(self, "has_font")
                box.prop(self, "has_displaytype")
                box.prop(self, "has_alignment")
                box.prop(self, "has_kern")
                box.prop(self, "has_speed")
                box.prop(self, "has_size")
                box.prop(self, "has_alpha")
                box.prop(self, "has_fadeintime")
                box.prop(self, "has_fadeouttime")
                box.prop(self, "has_width")
                box.prop(self, "has_height")
                box.prop(self, "has_widthscale")
                box.prop(self, "has_id")
                box.prop(self, "has_active")
                box.prop(self, "has_node")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_offset: layout.prop(self, "offset")
            if self.has_color: layout.prop(self, "color")
            if self.has_text: layout.prop(self, "text")
            if self.has_font: layout.prop(self, "font")
            if self.has_displaytype: layout.prop(self, "displaytype")
            if self.has_alignment: layout.prop(self, "alignment")
            if self.has_kern: layout.prop(self, "kern")
            if self.has_speed: layout.prop(self, "speed")
            if self.has_size: layout.prop(self, "size")
            if self.has_alpha: layout.prop(self, "alpha")
            if self.has_fadeintime: layout.prop(self, "fadeintime")
            if self.has_fadeouttime: layout.prop(self, "fadeouttime")
            if self.has_width: layout.prop(self, "width")
            if self.has_height: layout.prop(self, "height")
            if self.has_widthscale: layout.prop(self, "widthscale")
            if self.has_id: layout.prop(self, "id")
            if self.has_active: layout.prop(self, "active")
            if self.has_node: layout.prop(self, "node")

        def generate(self, obj):
            tag = f"<textdisplay4 componentguid='{self.componentguid}' "
            if self.has_id: tag += f"id='{self.id}' "
            if self.has_active: tag += f"active='{self.active}' "
            if self.has_width: tag += f"width='{self.width}' "
            if self.has_height: tag += f"height='{self.height}' "
            if self.has_text: tag += f"text='{self.text}' "
            if self.has_font: tag += f"font='{self.font}' "
            if self.has_size: tag += f"size='{self.size}' "
            if self.has_widthscale: tag += f"widthscale='{self.widthscale}' "
            if self.has_kern: tag += f"kern='{self.kern}' "
            if self.has_speed: tag += f"speed='{self.speed}' "
            if self.has_color: tag += f"color='{self.color[0]},{self.color[1]},{self.color[2]}' "
            if self.has_alpha: tag += f"alpha='{self.alpha}' "
            if self.has_node: tag += f"node='{self.node}' "
            if self.has_offset: tag += f"offset='{self.offset[0]},{self.offset[1]},{self.offset[2]}' "
            if self.has_fadeintime: tag += f"fadeintime='{self.fadeintime}' "
            if self.has_fadeouttime: tag += f"fadeouttime='{self.fadeouttime}' "
            if self.has_displaytype: tag += f"displaytype='{self.displaytype}' "
            if self.has_alignment: tag += f"alignment='{self.alignment}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class TextDisplay5(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_offset: BoolProperty(name="Offset", description="",default=True)
        has_color: BoolProperty(name="Color", description="",default=True)
        has_text: BoolProperty(name="Text", description="",default=True)
        has_font: BoolProperty(name="Font", description="",default=True)
        has_displaytype: BoolProperty(name="Display Type", description="",default=True)
        has_alignment: BoolProperty(name="Alignment", description="",default=True)
        has_kern: BoolProperty(name="Kern", description="",default=False)
        has_speed: BoolProperty(name="Speed", description="",default=True)
        has_size: BoolProperty(name="Size", description="",default=True)
        has_alpha: BoolProperty(name="Alpha", description="",default=True)
        has_fadeintime: BoolProperty(name="Fade In Time", description="",default=True)
        has_fadeouttime: BoolProperty(name="Fade Out Time", description="",default=True)
        has_width: BoolProperty(name="Width", description="",default=True)
        has_height: BoolProperty(name="Height", description="",default=True)
        has_widthscale: BoolProperty(name="Width Scale", description="",default=False)
        has_id: BoolProperty(name="Id", description="",default=True)
        has_active: BoolProperty(name="Active", description="",default=True)
        has_node: BoolProperty(name="Node", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        id: EnumProperty(
            name="Id", description="",
            items=[
                ("","","Found in Tag Template"),
                ("spooce","spooce","Generated from Real Data"),
                ("display","display","Generated from Real Data")
            ]
        )

        active: BoolProperty(
            name="Active", description="",
            default=True
        )

        width: FloatProperty(
            name="Width", description="",
            default=72
        )

        height: FloatProperty(
            name="Height", description="",
            default=15
        )

        text: StringProperty(
            name="Text", description="",
            default=""
        )

        font: EnumProperty(
            name="Font", description="",
            items=[
    
                ("Main","Main","Generated default with script"),
                ("LED","LED","Generated from Real Data"),
                ("native","Native","Generated from Real Data"),
                ("inventory","Inventory","Found in TagTemplate"),
                ("newled","New LED","Found in TagTemplate"),
                
            ],
            default="Main"
        )

        size: FloatProperty(
            name="Size", description="",
            default=5
        )

        widthscale: FloatProperty(
            name="Width Scale", description="",
            default=1
        )

        kern: FloatProperty(
            name="Kern", description="",
            default=-1
        )

        speed: FloatProperty(
            name="Speed", description="",
            default=0
        )

        color: FloatVectorProperty(
            name="Color", description="",
            subtype="COLOR",
            min=0, max=1,
            default=(1,1,1)
        )

        alpha: FloatProperty(
            name="Alpha", description="",
            default=1
        )

        node: StringProperty(
            name="Node", description="",
            default="none"
        )

        offset: FloatVectorProperty(
            name="Offset", description="",
            subtype="XYZ",
            default=(0,0,0)
        )

        fadeintime: FloatProperty(
            name="Fade In Time", description="",
            default=0.4
        )

        fadeouttime: FloatProperty(
            name="Fade Out Time", description="",
            default=0.8
        )

        displaytype: EnumProperty(
            name="Display Type", description="",
            items=[
                ("scrolling","scrolling","Generated default with script"),
                ("floating","Floating","Generated from Real Data"),
                ("static","Static","Generated from Real Data"),
                ("rising","Rising","Generated from Real Data")
            ],
            default="scrolling"
        )

        alignment: EnumProperty(
            name="Alignment", description="",
            items=[
                ("left","left","Generated default with script"),
                ("center","Center","Generated from Real Data"),
                ("right","Right","Found in TagTemplate"),
            ],
            default="left"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Text Display 5")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_offset")
                box.prop(self, "has_color")
                box.prop(self, "has_text")
                box.prop(self, "has_font")
                box.prop(self, "has_displaytype")
                box.prop(self, "has_alignment")
                box.prop(self, "has_kern")
                box.prop(self, "has_speed")
                box.prop(self, "has_size")
                box.prop(self, "has_alpha")
                box.prop(self, "has_fadeintime")
                box.prop(self, "has_fadeouttime")
                box.prop(self, "has_width")
                box.prop(self, "has_height")
                box.prop(self, "has_widthscale")
                box.prop(self, "has_id")
                box.prop(self, "has_active")
                box.prop(self, "has_node")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_offset: layout.prop(self, "offset")
            if self.has_color: layout.prop(self, "color")
            if self.has_text: layout.prop(self, "text")
            if self.has_font: layout.prop(self, "font")
            if self.has_displaytype: layout.prop(self, "displaytype")
            if self.has_alignment: layout.prop(self, "alignment")
            if self.has_kern: layout.prop(self, "kern")
            if self.has_speed: layout.prop(self, "speed")
            if self.has_size: layout.prop(self, "size")
            if self.has_alpha: layout.prop(self, "alpha")
            if self.has_fadeintime: layout.prop(self, "fadeintime")
            if self.has_fadeouttime: layout.prop(self, "fadeouttime")
            if self.has_width: layout.prop(self, "width")
            if self.has_height: layout.prop(self, "height")
            if self.has_widthscale: layout.prop(self, "widthscale")
            if self.has_id: layout.prop(self, "id")
            if self.has_active: layout.prop(self, "active")
            if self.has_node: layout.prop(self, "node")

        def generate(self, obj):
            tag = f"<textdisplay5 componentguid='{self.componentguid}' "
            if self.has_id: tag += f"id='{self.id}' "
            if self.has_active: tag += f"active='{self.active}' "
            if self.has_width: tag += f"width='{self.width}' "
            if self.has_height: tag += f"height='{self.height}' "
            if self.has_text: tag += f"text='{self.text}' "
            if self.has_font: tag += f"font='{self.font}' "
            if self.has_size: tag += f"size='{self.size}' "
            if self.has_widthscale: tag += f"widthscale='{self.widthscale}' "
            if self.has_kern: tag += f"kern='{self.kern}' "
            if self.has_speed: tag += f"speed='{self.speed}' "
            if self.has_color: tag += f"color='{self.color[0]},{self.color[1]},{self.color[2]}' "
            if self.has_alpha: tag += f"alpha='{self.alpha}' "
            if self.has_node: tag += f"node='{self.node}' "
            if self.has_offset: tag += f"offset='{self.offset[0]},{self.offset[1]},{self.offset[2]}' "
            if self.has_fadeintime: tag += f"fadeintime='{self.fadeintime}' "
            if self.has_fadeouttime: tag += f"fadeouttime='{self.fadeouttime}' "
            if self.has_displaytype: tag += f"displaytype='{self.displaytype}' "
            if self.has_alignment: tag += f"alignment='{self.alignment}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class TextDisplay6(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_offset: BoolProperty(name="Offset", description="",default=True)
        has_color: BoolProperty(name="Color", description="",default=True)
        has_text: BoolProperty(name="Text", description="",default=True)
        has_font: BoolProperty(name="Font", description="",default=True)
        has_displaytype: BoolProperty(name="Display Type", description="",default=True)
        has_alignment: BoolProperty(name="Alignment", description="",default=True)
        has_kern: BoolProperty(name="Kern", description="",default=False)
        has_speed: BoolProperty(name="Speed", description="",default=True)
        has_size: BoolProperty(name="Size", description="",default=True)
        has_alpha: BoolProperty(name="Alpha", description="",default=True)
        has_fadeintime: BoolProperty(name="Fade In Time", description="",default=True)
        has_fadeouttime: BoolProperty(name="Fade Out Time", description="",default=True)
        has_width: BoolProperty(name="Width", description="",default=True)
        has_height: BoolProperty(name="Height", description="",default=True)
        has_widthscale: BoolProperty(name="Width Scale", description="",default=False)
        has_id: BoolProperty(name="Id", description="",default=True)
        has_active: BoolProperty(name="Active", description="",default=True)
        has_node: BoolProperty(name="Node", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        id: EnumProperty(
            name="Id", description="",
            items=[
                ("","","Found in Tag Template"),
                ("spooce","spooce","Generated from Real Data"),
                ("display","display","Generated from Real Data")
            ]
        )

        active: BoolProperty(
            name="Active", description="",
            default=True
        )

        width: FloatProperty(
            name="Width", description="",
            default=72
        )

        height: FloatProperty(
            name="Height", description="",
            default=15
        )

        text: StringProperty(
            name="Text", description="",
            default=""
        )

        font: EnumProperty(
            name="Font", description="",
            items=[
    
                ("Main","Main","Generated default with script"),
                ("LED","LED","Generated from Real Data"),
                ("native","Native","Generated from Real Data"),
                ("inventory","Inventory","Found in TagTemplate"),
                ("newled","New LED","Found in TagTemplate"),
                
            ],
            default="Main"
        )

        size: FloatProperty(
            name="Size", description="",
            default=5
        )

        widthscale: FloatProperty(
            name="Width Scale", description="",
            default=1
        )

        kern: FloatProperty(
            name="Kern", description="",
            default=-1
        )

        speed: FloatProperty(
            name="Speed", description="",
            default=0
        )

        color: FloatVectorProperty(
            name="Color", description="",
            subtype="COLOR",
            min=0, max=1,
            default=(1,1,1)
        )

        alpha: FloatProperty(
            name="Alpha", description="",
            default=1
        )

        node: StringProperty(
            name="Node", description="",
            default="none"
        )

        offset: FloatVectorProperty(
            name="Offset", description="",
            subtype="XYZ",
            default=(0,0,0)
        )

        fadeintime: FloatProperty(
            name="Fade In Time", description="",
            default=0.4
        )

        fadeouttime: FloatProperty(
            name="Fade Out Time", description="",
            default=0.8
        )

        displaytype: EnumProperty(
            name="Display Type", description="",
            items=[
                ("scrolling","scrolling","Generated default with script"),
                ("floating","Floating","Generated from Real Data"),
                ("static","Static","Generated from Real Data"),
                ("rising","Rising","Generated from Real Data")
            ],
            default="scrolling"
        )

        alignment: EnumProperty(
            name="Alignment", description="",
            items=[
                ("left","left","Generated default with script"),
                ("center","Center","Generated from Real Data"),
                ("right","Right","Found in TagTemplate"),
            ],
            default="left"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Text Display 6")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_offset")
                box.prop(self, "has_color")
                box.prop(self, "has_text")
                box.prop(self, "has_font")
                box.prop(self, "has_displaytype")
                box.prop(self, "has_alignment")
                box.prop(self, "has_kern")
                box.prop(self, "has_speed")
                box.prop(self, "has_size")
                box.prop(self, "has_alpha")
                box.prop(self, "has_fadeintime")
                box.prop(self, "has_fadeouttime")
                box.prop(self, "has_width")
                box.prop(self, "has_height")
                box.prop(self, "has_widthscale")
                box.prop(self, "has_id")
                box.prop(self, "has_active")
                box.prop(self, "has_node")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_offset: layout.prop(self, "offset")
            if self.has_color: layout.prop(self, "color")
            if self.has_text: layout.prop(self, "text")
            if self.has_font: layout.prop(self, "font")
            if self.has_displaytype: layout.prop(self, "displaytype")
            if self.has_alignment: layout.prop(self, "alignment")
            if self.has_kern: layout.prop(self, "kern")
            if self.has_speed: layout.prop(self, "speed")
            if self.has_size: layout.prop(self, "size")
            if self.has_alpha: layout.prop(self, "alpha")
            if self.has_fadeintime: layout.prop(self, "fadeintime")
            if self.has_fadeouttime: layout.prop(self, "fadeouttime")
            if self.has_width: layout.prop(self, "width")
            if self.has_height: layout.prop(self, "height")
            if self.has_widthscale: layout.prop(self, "widthscale")
            if self.has_id: layout.prop(self, "id")
            if self.has_active: layout.prop(self, "active")
            if self.has_node: layout.prop(self, "node")

        def generate(self, obj):
            tag = f"<textdisplay6 componentguid='{self.componentguid}' "
            if self.has_id: tag += f"id='{self.id}' "
            if self.has_active: tag += f"active='{self.active}' "
            if self.has_width: tag += f"width='{self.width}' "
            if self.has_height: tag += f"height='{self.height}' "
            if self.has_text: tag += f"text='{self.text}' "
            if self.has_font: tag += f"font='{self.font}' "
            if self.has_size: tag += f"size='{self.size}' "
            if self.has_widthscale: tag += f"widthscale='{self.widthscale}' "
            if self.has_kern: tag += f"kern='{self.kern}' "
            if self.has_speed: tag += f"speed='{self.speed}' "
            if self.has_color: tag += f"color='{self.color[0]},{self.color[1]},{self.color[2]}' "
            if self.has_alpha: tag += f"alpha='{self.alpha}' "
            if self.has_node: tag += f"node='{self.node}' "
            if self.has_offset: tag += f"offset='{self.offset[0]},{self.offset[1]},{self.offset[2]}' "
            if self.has_fadeintime: tag += f"fadeintime='{self.fadeintime}' "
            if self.has_fadeouttime: tag += f"fadeouttime='{self.fadeouttime}' "
            if self.has_displaytype: tag += f"displaytype='{self.displaytype}' "
            if self.has_alignment: tag += f"alignment='{self.alignment}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class TextDisplay7(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_offset: BoolProperty(name="Offset", description="",default=True)
        has_color: BoolProperty(name="Color", description="",default=True)
        has_text: BoolProperty(name="Text", description="",default=True)
        has_font: BoolProperty(name="Font", description="",default=True)
        has_displaytype: BoolProperty(name="Display Type", description="",default=True)
        has_alignment: BoolProperty(name="Alignment", description="",default=True)
        has_kern: BoolProperty(name="Kern", description="",default=False)
        has_speed: BoolProperty(name="Speed", description="",default=True)
        has_size: BoolProperty(name="Size", description="",default=True)
        has_alpha: BoolProperty(name="Alpha", description="",default=True)
        has_fadeintime: BoolProperty(name="Fade In Time", description="",default=True)
        has_fadeouttime: BoolProperty(name="Fade Out Time", description="",default=True)
        has_width: BoolProperty(name="Width", description="",default=True)
        has_height: BoolProperty(name="Height", description="",default=True)
        has_widthscale: BoolProperty(name="Width Scale", description="",default=False)
        has_id: BoolProperty(name="Id", description="",default=True)
        has_active: BoolProperty(name="Active", description="",default=True)
        has_node: BoolProperty(name="Node", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        id: EnumProperty(
            name="Id", description="",
            items=[
                ("","","Found in Tag Template"),
                ("spooce","spooce","Generated from Real Data"),
                ("display","display","Generated from Real Data")
            ]
        )

        active: BoolProperty(
            name="Active", description="",
            default=True
        )

        width: FloatProperty(
            name="Width", description="",
            default=72
        )

        height: FloatProperty(
            name="Height", description="",
            default=15
        )

        text: StringProperty(
            name="Text", description="",
            default=""
        )

        font: EnumProperty(
            name="Font", description="",
            items=[
    
                ("Main","Main","Generated default with script"),
                ("LED","LED","Generated from Real Data"),
                ("native","Native","Generated from Real Data"),
                ("inventory","Inventory","Found in TagTemplate"),
                ("newled","New LED","Found in TagTemplate"),
                
            ],
            default="Main"
        )

        size: FloatProperty(
            name="Size", description="",
            default=5
        )

        widthscale: FloatProperty(
            name="Width Scale", description="",
            default=1
        )

        kern: FloatProperty(
            name="Kern", description="",
            default=-1
        )

        speed: FloatProperty(
            name="Speed", description="",
            default=0
        )

        color: FloatVectorProperty(
            name="Color", description="",
            subtype="COLOR",
            min=0, max=1,
            default=(1,1,1)
        )

        alpha: FloatProperty(
            name="Alpha", description="",
            default=1
        )

        node: StringProperty(
            name="Node", description="",
            default="none"
        )

        offset: FloatVectorProperty(
            name="Offset", description="",
            subtype="XYZ",
            default=(0,0,0)
        )

        fadeintime: FloatProperty(
            name="Fade In Time", description="",
            default=0.4
        )

        fadeouttime: FloatProperty(
            name="Fade Out Time", description="",
            default=0.8
        )

        displaytype: EnumProperty(
            name="Display Type", description="",
            items=[
                ("scrolling","scrolling","Generated default with script"),
                ("floating","Floating","Generated from Real Data"),
                ("static","Static","Generated from Real Data"),
                ("rising","Rising","Generated from Real Data")
            ],
            default="scrolling"
        )

        alignment: EnumProperty(
            name="Alignment", description="",
            items=[
                ("left","left","Generated default with script"),
                ("center","Center","Generated from Real Data"),
                ("right","Right","Found in TagTemplate"),
            ],
            default="left"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Text Display 7")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_offset")
                box.prop(self, "has_color")
                box.prop(self, "has_text")
                box.prop(self, "has_font")
                box.prop(self, "has_displaytype")
                box.prop(self, "has_alignment")
                box.prop(self, "has_kern")
                box.prop(self, "has_speed")
                box.prop(self, "has_size")
                box.prop(self, "has_alpha")
                box.prop(self, "has_fadeintime")
                box.prop(self, "has_fadeouttime")
                box.prop(self, "has_width")
                box.prop(self, "has_height")
                box.prop(self, "has_widthscale")
                box.prop(self, "has_id")
                box.prop(self, "has_active")
                box.prop(self, "has_node")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_offset: layout.prop(self, "offset")
            if self.has_color: layout.prop(self, "color")
            if self.has_text: layout.prop(self, "text")
            if self.has_font: layout.prop(self, "font")
            if self.has_displaytype: layout.prop(self, "displaytype")
            if self.has_alignment: layout.prop(self, "alignment")
            if self.has_kern: layout.prop(self, "kern")
            if self.has_speed: layout.prop(self, "speed")
            if self.has_size: layout.prop(self, "size")
            if self.has_alpha: layout.prop(self, "alpha")
            if self.has_fadeintime: layout.prop(self, "fadeintime")
            if self.has_fadeouttime: layout.prop(self, "fadeouttime")
            if self.has_width: layout.prop(self, "width")
            if self.has_height: layout.prop(self, "height")
            if self.has_widthscale: layout.prop(self, "widthscale")
            if self.has_id: layout.prop(self, "id")
            if self.has_active: layout.prop(self, "active")
            if self.has_node: layout.prop(self, "node")

        def generate(self, obj):
            tag = f"<textdisplay7 componentguid='{self.componentguid}' "
            if self.has_id: tag += f"id='{self.id}' "
            if self.has_active: tag += f"active='{self.active}' "
            if self.has_width: tag += f"width='{self.width}' "
            if self.has_height: tag += f"height='{self.height}' "
            if self.has_text: tag += f"text='{self.text}' "
            if self.has_font: tag += f"font='{self.font}' "
            if self.has_size: tag += f"size='{self.size}' "
            if self.has_widthscale: tag += f"widthscale='{self.widthscale}' "
            if self.has_kern: tag += f"kern='{self.kern}' "
            if self.has_speed: tag += f"speed='{self.speed}' "
            if self.has_color: tag += f"color='{self.color[0]},{self.color[1]},{self.color[2]}' "
            if self.has_alpha: tag += f"alpha='{self.alpha}' "
            if self.has_node: tag += f"node='{self.node}' "
            if self.has_offset: tag += f"offset='{self.offset[0]},{self.offset[1]},{self.offset[2]}' "
            if self.has_fadeintime: tag += f"fadeintime='{self.fadeintime}' "
            if self.has_fadeouttime: tag += f"fadeouttime='{self.fadeouttime}' "
            if self.has_displaytype: tag += f"displaytype='{self.displaytype}' "
            if self.has_alignment: tag += f"alignment='{self.alignment}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class TextDisplay8(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_offset: BoolProperty(name="Offset", description="",default=True)
        has_color: BoolProperty(name="Color", description="",default=True)
        has_text: BoolProperty(name="Text", description="",default=True)
        has_font: BoolProperty(name="Font", description="",default=True)
        has_displaytype: BoolProperty(name="Display Type", description="",default=True)
        has_alignment: BoolProperty(name="Alignment", description="",default=True)
        has_kern: BoolProperty(name="Kern", description="",default=False)
        has_speed: BoolProperty(name="Speed", description="",default=True)
        has_size: BoolProperty(name="Size", description="",default=True)
        has_alpha: BoolProperty(name="Alpha", description="",default=True)
        has_fadeintime: BoolProperty(name="Fade In Time", description="",default=True)
        has_fadeouttime: BoolProperty(name="Fade Out Time", description="",default=True)
        has_width: BoolProperty(name="Width", description="",default=True)
        has_height: BoolProperty(name="Height", description="",default=True)
        has_widthscale: BoolProperty(name="Width Scale", description="",default=False)
        has_id: BoolProperty(name="Id", description="",default=True)
        has_active: BoolProperty(name="Active", description="",default=True)
        has_node: BoolProperty(name="Node", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        id: EnumProperty(
            name="Id", description="",
            items=[
                ("","","Found in Tag Template"),
                ("spooce","spooce","Generated from Real Data"),
                ("display","display","Generated from Real Data")
            ]
        )

        active: BoolProperty(
            name="Active", description="",
            default=True
        )

        width: FloatProperty(
            name="Width", description="",
            default=72
        )

        height: FloatProperty(
            name="Height", description="",
            default=15
        )

        text: StringProperty(
            name="Text", description="",
            default=""
        )

        font: EnumProperty(
            name="Font", description="",
            items=[
    
                ("Main","Main","Generated default with script"),
                ("LED","LED","Generated from Real Data"),
                ("native","Native","Generated from Real Data"),
                ("inventory","Inventory","Found in TagTemplate"),
                ("newled","New LED","Found in TagTemplate"),
                
            ],
            default="Main"
        )

        size: FloatProperty(
            name="Size", description="",
            default=5
        )

        widthscale: FloatProperty(
            name="Width Scale", description="",
            default=1
        )

        kern: FloatProperty(
            name="Kern", description="",
            default=-1
        )

        speed: FloatProperty(
            name="Speed", description="",
            default=0
        )

        color: FloatVectorProperty(
            name="Color", description="",
            subtype="COLOR",
            min=0, max=1,
            default=(1,1,1)
        )

        alpha: FloatProperty(
            name="Alpha", description="",
            default=1
        )

        node: StringProperty(
            name="Node", description="",
            default="none"
        )

        offset: FloatVectorProperty(
            name="Offset", description="",
            subtype="XYZ",
            default=(0,0,0)
        )

        fadeintime: FloatProperty(
            name="Fade In Time", description="",
            default=0.4
        )

        fadeouttime: FloatProperty(
            name="Fade Out Time", description="",
            default=0.8
        )

        displaytype: EnumProperty(
            name="Display Type", description="",
            items=[
                ("scrolling","scrolling","Generated default with script"),
                ("floating","Floating","Generated from Real Data"),
                ("static","Static","Generated from Real Data"),
                ("rising","Rising","Generated from Real Data")
            ],
            default="scrolling"
        )

        alignment: EnumProperty(
            name="Alignment", description="",
            items=[
                ("left","left","Generated default with script"),
                ("center","Center","Generated from Real Data"),
                ("right","Right","Found in TagTemplate"),
            ],
            default="left"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Text Display 8")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_offset")
                box.prop(self, "has_color")
                box.prop(self, "has_text")
                box.prop(self, "has_font")
                box.prop(self, "has_displaytype")
                box.prop(self, "has_alignment")
                box.prop(self, "has_kern")
                box.prop(self, "has_speed")
                box.prop(self, "has_size")
                box.prop(self, "has_alpha")
                box.prop(self, "has_fadeintime")
                box.prop(self, "has_fadeouttime")
                box.prop(self, "has_width")
                box.prop(self, "has_height")
                box.prop(self, "has_widthscale")
                box.prop(self, "has_id")
                box.prop(self, "has_active")
                box.prop(self, "has_node")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_offset: layout.prop(self, "offset")
            if self.has_color: layout.prop(self, "color")
            if self.has_text: layout.prop(self, "text")
            if self.has_font: layout.prop(self, "font")
            if self.has_displaytype: layout.prop(self, "displaytype")
            if self.has_alignment: layout.prop(self, "alignment")
            if self.has_kern: layout.prop(self, "kern")
            if self.has_speed: layout.prop(self, "speed")
            if self.has_size: layout.prop(self, "size")
            if self.has_alpha: layout.prop(self, "alpha")
            if self.has_fadeintime: layout.prop(self, "fadeintime")
            if self.has_fadeouttime: layout.prop(self, "fadeouttime")
            if self.has_width: layout.prop(self, "width")
            if self.has_height: layout.prop(self, "height")
            if self.has_widthscale: layout.prop(self, "widthscale")
            if self.has_id: layout.prop(self, "id")
            if self.has_active: layout.prop(self, "active")
            if self.has_node: layout.prop(self, "node")

        def generate(self, obj):
            tag = f"<textdisplay8 componentguid='{self.componentguid}' "
            if self.has_id: tag += f"id='{self.id}' "
            if self.has_active: tag += f"active='{self.active}' "
            if self.has_width: tag += f"width='{self.width}' "
            if self.has_height: tag += f"height='{self.height}' "
            if self.has_text: tag += f"text='{self.text}' "
            if self.has_font: tag += f"font='{self.font}' "
            if self.has_size: tag += f"size='{self.size}' "
            if self.has_widthscale: tag += f"widthscale='{self.widthscale}' "
            if self.has_kern: tag += f"kern='{self.kern}' "
            if self.has_speed: tag += f"speed='{self.speed}' "
            if self.has_color: tag += f"color='{self.color[0]},{self.color[1]},{self.color[2]}' "
            if self.has_alpha: tag += f"alpha='{self.alpha}' "
            if self.has_node: tag += f"node='{self.node}' "
            if self.has_offset: tag += f"offset='{self.offset[0]},{self.offset[1]},{self.offset[2]}' "
            if self.has_fadeintime: tag += f"fadeintime='{self.fadeintime}' "
            if self.has_fadeouttime: tag += f"fadeouttime='{self.fadeouttime}' "
            if self.has_displaytype: tag += f"displaytype='{self.displaytype}' "
            if self.has_alignment: tag += f"alignment='{self.alignment}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class TextDisplay9(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_offset: BoolProperty(name="Offset", description="",default=True)
        has_color: BoolProperty(name="Color", description="",default=True)
        has_text: BoolProperty(name="Text", description="",default=True)
        has_font: BoolProperty(name="Font", description="",default=True)
        has_displaytype: BoolProperty(name="Display Type", description="",default=True)
        has_alignment: BoolProperty(name="Alignment", description="",default=True)
        has_kern: BoolProperty(name="Kern", description="",default=False)
        has_speed: BoolProperty(name="Speed", description="",default=True)
        has_size: BoolProperty(name="Size", description="",default=True)
        has_alpha: BoolProperty(name="Alpha", description="",default=True)
        has_fadeintime: BoolProperty(name="Fade In Time", description="",default=True)
        has_fadeouttime: BoolProperty(name="Fade Out Time", description="",default=True)
        has_width: BoolProperty(name="Width", description="",default=True)
        has_height: BoolProperty(name="Height", description="",default=True)
        has_widthscale: BoolProperty(name="Width Scale", description="",default=False)
        has_id: BoolProperty(name="Id", description="",default=True)
        has_active: BoolProperty(name="Active", description="",default=True)
        has_node: BoolProperty(name="Node", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        id: EnumProperty(
            name="Id", description="",
            items=[
                ("","","Found in Tag Template"),
                ("spooce","spooce","Generated from Real Data"),
                ("display","display","Generated from Real Data")
            ]
        )

        active: BoolProperty(
            name="Active", description="",
            default=True
        )

        width: FloatProperty(
            name="Width", description="",
            default=72
        )

        height: FloatProperty(
            name="Height", description="",
            default=15
        )

        text: StringProperty(
            name="Text", description="",
            default=""
        )

        font: EnumProperty(
            name="Font", description="",
            items=[
    
                ("Main","Main","Generated default with script"),
                ("LED","LED","Generated from Real Data"),
                ("native","Native","Generated from Real Data"),
                ("inventory","Inventory","Found in TagTemplate"),
                ("newled","New LED","Found in TagTemplate"),
                
            ],
            default="Main"
        )

        size: FloatProperty(
            name="Size", description="",
            default=5
        )

        widthscale: FloatProperty(
            name="Width Scale", description="",
            default=1
        )

        kern: FloatProperty(
            name="Kern", description="",
            default=-1
        )

        speed: FloatProperty(
            name="Speed", description="",
            default=0
        )

        color: FloatVectorProperty(
            name="Color", description="",
            subtype="COLOR",
            min=0, max=1,
            default=(1,1,1)
        )

        alpha: FloatProperty(
            name="Alpha", description="",
            default=1
        )

        node: StringProperty(
            name="Node", description="",
            default="none"
        )

        offset: FloatVectorProperty(
            name="Offset", description="",
            subtype="XYZ",
            default=(0,0,0)
        )

        fadeintime: FloatProperty(
            name="Fade In Time", description="",
            default=0.4
        )

        fadeouttime: FloatProperty(
            name="Fade Out Time", description="",
            default=0.8
        )

        displaytype: EnumProperty(
            name="Display Type", description="",
            items=[
                ("scrolling","scrolling","Generated default with script"),
                ("floating","Floating","Generated from Real Data"),
                ("static","Static","Generated from Real Data"),
                ("rising","Rising","Generated from Real Data")
            ],
            default="scrolling"
        )

        alignment: EnumProperty(
            name="Alignment", description="",
            items=[
                ("left","left","Generated default with script"),
                ("center","Center","Generated from Real Data"),
                ("right","Right","Found in TagTemplate"),
            ],
            default="left"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Text Display 9")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_offset")
                box.prop(self, "has_color")
                box.prop(self, "has_text")
                box.prop(self, "has_font")
                box.prop(self, "has_displaytype")
                box.prop(self, "has_alignment")
                box.prop(self, "has_kern")
                box.prop(self, "has_speed")
                box.prop(self, "has_size")
                box.prop(self, "has_alpha")
                box.prop(self, "has_fadeintime")
                box.prop(self, "has_fadeouttime")
                box.prop(self, "has_width")
                box.prop(self, "has_height")
                box.prop(self, "has_widthscale")
                box.prop(self, "has_id")
                box.prop(self, "has_active")
                box.prop(self, "has_node")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_offset: layout.prop(self, "offset")
            if self.has_color: layout.prop(self, "color")
            if self.has_text: layout.prop(self, "text")
            if self.has_font: layout.prop(self, "font")
            if self.has_displaytype: layout.prop(self, "displaytype")
            if self.has_alignment: layout.prop(self, "alignment")
            if self.has_kern: layout.prop(self, "kern")
            if self.has_speed: layout.prop(self, "speed")
            if self.has_size: layout.prop(self, "size")
            if self.has_alpha: layout.prop(self, "alpha")
            if self.has_fadeintime: layout.prop(self, "fadeintime")
            if self.has_fadeouttime: layout.prop(self, "fadeouttime")
            if self.has_width: layout.prop(self, "width")
            if self.has_height: layout.prop(self, "height")
            if self.has_widthscale: layout.prop(self, "widthscale")
            if self.has_id: layout.prop(self, "id")
            if self.has_active: layout.prop(self, "active")
            if self.has_node: layout.prop(self, "node")

        def generate(self, obj):
            tag = f"<textdisplay9 componentguid='{self.componentguid}' "
            if self.has_id: tag += f"id='{self.id}' "
            if self.has_active: tag += f"active='{self.active}' "
            if self.has_width: tag += f"width='{self.width}' "
            if self.has_height: tag += f"height='{self.height}' "
            if self.has_text: tag += f"text='{self.text}' "
            if self.has_font: tag += f"font='{self.font}' "
            if self.has_size: tag += f"size='{self.size}' "
            if self.has_widthscale: tag += f"widthscale='{self.widthscale}' "
            if self.has_kern: tag += f"kern='{self.kern}' "
            if self.has_speed: tag += f"speed='{self.speed}' "
            if self.has_color: tag += f"color='{self.color[0]},{self.color[1]},{self.color[2]}' "
            if self.has_alpha: tag += f"alpha='{self.alpha}' "
            if self.has_node: tag += f"node='{self.node}' "
            if self.has_offset: tag += f"offset='{self.offset[0]},{self.offset[1]},{self.offset[2]}' "
            if self.has_fadeintime: tag += f"fadeintime='{self.fadeintime}' "
            if self.has_fadeouttime: tag += f"fadeouttime='{self.fadeouttime}' "
            if self.has_displaytype: tag += f"displaytype='{self.displaytype}' "
            if self.has_alignment: tag += f"alignment='{self.alignment}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class TextDisplay10(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_offset: BoolProperty(name="Offset", description="",default=True)
        has_color: BoolProperty(name="Color", description="",default=True)
        has_text: BoolProperty(name="Text", description="",default=True)
        has_font: BoolProperty(name="Font", description="",default=True)
        has_displaytype: BoolProperty(name="Display Type", description="",default=True)
        has_alignment: BoolProperty(name="Alignment", description="",default=True)
        has_kern: BoolProperty(name="Kern", description="",default=False)
        has_speed: BoolProperty(name="Speed", description="",default=True)
        has_size: BoolProperty(name="Size", description="",default=True)
        has_alpha: BoolProperty(name="Alpha", description="",default=True)
        has_fadeintime: BoolProperty(name="Fade In Time", description="",default=True)
        has_fadeouttime: BoolProperty(name="Fade Out Time", description="",default=True)
        has_width: BoolProperty(name="Width", description="",default=True)
        has_height: BoolProperty(name="Height", description="",default=True)
        has_widthscale: BoolProperty(name="Width Scale", description="",default=False)
        has_id: BoolProperty(name="Id", description="",default=True)
        has_active: BoolProperty(name="Active", description="",default=True)
        has_node: BoolProperty(name="Node", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        id: EnumProperty(
            name="Id", description="",
            items=[
                ("","","Found in Tag Template"),
                ("spooce","spooce","Generated from Real Data"),
                ("display","display","Generated from Real Data")
            ]
        )

        active: BoolProperty(
            name="Active", description="",
            default=True
        )

        width: FloatProperty(
            name="Width", description="",
            default=72
        )

        height: FloatProperty(
            name="Height", description="",
            default=15
        )

        text: StringProperty(
            name="Text", description="",
            default=""
        )

        font: EnumProperty(
            name="Font", description="",
            items=[
    
                ("Main","Main","Generated default with script"),
                ("LED","LED","Generated from Real Data"),
                ("native","Native","Generated from Real Data"),
                ("inventory","Inventory","Found in TagTemplate"),
                ("newled","New LED","Found in TagTemplate"),
                
            ],
            default="Main"
        )

        size: FloatProperty(
            name="Size", description="",
            default=5
        )

        widthscale: FloatProperty(
            name="Width Scale", description="",
            default=1
        )

        kern: FloatProperty(
            name="Kern", description="",
            default=-1
        )

        speed: FloatProperty(
            name="Speed", description="",
            default=0
        )

        color: FloatVectorProperty(
            name="Color", description="",
            subtype="COLOR",
            min=0, max=1,
            default=(1,1,1)
        )

        alpha: FloatProperty(
            name="Alpha", description="",
            default=1
        )

        node: StringProperty(
            name="Node", description="",
            default="none"
        )

        offset: FloatVectorProperty(
            name="Offset", description="",
            subtype="XYZ",
            default=(0,0,0)
        )

        fadeintime: FloatProperty(
            name="Fade In Time", description="",
            default=0.4
        )

        fadeouttime: FloatProperty(
            name="Fade Out Time", description="",
            default=0.8
        )

        displaytype: EnumProperty(
            name="Display Type", description="",
            items=[
                ("scrolling","scrolling","Generated default with script"),
                ("floating","Floating","Generated from Real Data"),
                ("static","Static","Generated from Real Data"),
                ("rising","Rising","Generated from Real Data")
            ],
            default="scrolling"
        )

        alignment: EnumProperty(
            name="Alignment", description="",
            items=[
                ("left","left","Generated default with script"),
                ("center","Center","Generated from Real Data"),
                ("right","Right","Found in TagTemplate"),
            ],
            default="left"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Text Display 10")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_offset")
                box.prop(self, "has_color")
                box.prop(self, "has_text")
                box.prop(self, "has_font")
                box.prop(self, "has_displaytype")
                box.prop(self, "has_alignment")
                box.prop(self, "has_kern")
                box.prop(self, "has_speed")
                box.prop(self, "has_size")
                box.prop(self, "has_alpha")
                box.prop(self, "has_fadeintime")
                box.prop(self, "has_fadeouttime")
                box.prop(self, "has_width")
                box.prop(self, "has_height")
                box.prop(self, "has_widthscale")
                box.prop(self, "has_id")
                box.prop(self, "has_active")
                box.prop(self, "has_node")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_offset: layout.prop(self, "offset")
            if self.has_color: layout.prop(self, "color")
            if self.has_text: layout.prop(self, "text")
            if self.has_font: layout.prop(self, "font")
            if self.has_displaytype: layout.prop(self, "displaytype")
            if self.has_alignment: layout.prop(self, "alignment")
            if self.has_kern: layout.prop(self, "kern")
            if self.has_speed: layout.prop(self, "speed")
            if self.has_size: layout.prop(self, "size")
            if self.has_alpha: layout.prop(self, "alpha")
            if self.has_fadeintime: layout.prop(self, "fadeintime")
            if self.has_fadeouttime: layout.prop(self, "fadeouttime")
            if self.has_width: layout.prop(self, "width")
            if self.has_height: layout.prop(self, "height")
            if self.has_widthscale: layout.prop(self, "widthscale")
            if self.has_id: layout.prop(self, "id")
            if self.has_active: layout.prop(self, "active")
            if self.has_node: layout.prop(self, "node")

        def generate(self, obj):
            tag = f"<textdisplay10 componentguid='{self.componentguid}' "
            if self.has_id: tag += f"id='{self.id}' "
            if self.has_active: tag += f"active='{self.active}' "
            if self.has_width: tag += f"width='{self.width}' "
            if self.has_height: tag += f"height='{self.height}' "
            if self.has_text: tag += f"text='{self.text}' "
            if self.has_font: tag += f"font='{self.font}' "
            if self.has_size: tag += f"size='{self.size}' "
            if self.has_widthscale: tag += f"widthscale='{self.widthscale}' "
            if self.has_kern: tag += f"kern='{self.kern}' "
            if self.has_speed: tag += f"speed='{self.speed}' "
            if self.has_color: tag += f"color='{self.color[0]},{self.color[1]},{self.color[2]}' "
            if self.has_alpha: tag += f"alpha='{self.alpha}' "
            if self.has_node: tag += f"node='{self.node}' "
            if self.has_offset: tag += f"offset='{self.offset[0]},{self.offset[1]},{self.offset[2]}' "
            if self.has_fadeintime: tag += f"fadeintime='{self.fadeintime}' "
            if self.has_fadeouttime: tag += f"fadeouttime='{self.fadeouttime}' "
            if self.has_displaytype: tag += f"displaytype='{self.displaytype}' "
            if self.has_alignment: tag += f"alignment='{self.alignment}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class TextDisplay11(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_offset: BoolProperty(name="Offset", description="",default=True)
        has_color: BoolProperty(name="Color", description="",default=True)
        has_text: BoolProperty(name="Text", description="",default=True)
        has_font: BoolProperty(name="Font", description="",default=True)
        has_displaytype: BoolProperty(name="Display Type", description="",default=True)
        has_alignment: BoolProperty(name="Alignment", description="",default=True)
        has_kern: BoolProperty(name="Kern", description="",default=False)
        has_speed: BoolProperty(name="Speed", description="",default=True)
        has_size: BoolProperty(name="Size", description="",default=True)
        has_alpha: BoolProperty(name="Alpha", description="",default=True)
        has_fadeintime: BoolProperty(name="Fade In Time", description="",default=True)
        has_fadeouttime: BoolProperty(name="Fade Out Time", description="",default=True)
        has_width: BoolProperty(name="Width", description="",default=True)
        has_height: BoolProperty(name="Height", description="",default=True)
        has_widthscale: BoolProperty(name="Width Scale", description="",default=False)
        has_id: BoolProperty(name="Id", description="",default=True)
        has_active: BoolProperty(name="Active", description="",default=True)
        has_node: BoolProperty(name="Node", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        id: EnumProperty(
            name="Id", description="",
            items=[
                ("","","Found in Tag Template"),
                ("spooce","spooce","Generated from Real Data"),
                ("display","display","Generated from Real Data")
            ]
        )

        active: BoolProperty(
            name="Active", description="",
            default=True
        )

        width: FloatProperty(
            name="Width", description="",
            default=72
        )

        height: FloatProperty(
            name="Height", description="",
            default=15
        )

        text: StringProperty(
            name="Text", description="",
            default=""
        )

        font: EnumProperty(
            name="Font", description="",
            items=[
    
                ("Main","Main","Generated default with script"),
                ("LED","LED","Generated from Real Data"),
                ("native","Native","Generated from Real Data"),
                ("inventory","Inventory","Found in TagTemplate"),
                ("newled","New LED","Found in TagTemplate"),
                
            ],
            default="Main"
        )

        size: FloatProperty(
            name="Size", description="",
            default=5
        )

        widthscale: FloatProperty(
            name="Width Scale", description="",
            default=1
        )

        kern: FloatProperty(
            name="Kern", description="",
            default=-1
        )

        speed: FloatProperty(
            name="Speed", description="",
            default=0
        )

        color: FloatVectorProperty(
            name="Color", description="",
            subtype="COLOR",
            min=0, max=1,
            default=(1,1,1)
        )

        alpha: FloatProperty(
            name="Alpha", description="",
            default=1
        )

        node: StringProperty(
            name="Node", description="",
            default="none"
        )

        offset: FloatVectorProperty(
            name="Offset", description="",
            subtype="XYZ",
            default=(0,0,0)
        )

        fadeintime: FloatProperty(
            name="Fade In Time", description="",
            default=0.4
        )

        fadeouttime: FloatProperty(
            name="Fade Out Time", description="",
            default=0.8
        )

        displaytype: EnumProperty(
            name="Display Type", description="",
            items=[
                ("scrolling","scrolling","Generated default with script"),
                ("floating","Floating","Generated from Real Data"),
                ("static","Static","Generated from Real Data"),
                ("rising","Rising","Generated from Real Data")
            ],
            default="scrolling"
        )

        alignment: EnumProperty(
            name="Alignment", description="",
            items=[
                ("left","left","Generated default with script"),
                ("center","Center","Generated from Real Data"),
                ("right","Right","Found in TagTemplate"),
            ],
            default="left"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Text Display 11")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_offset")
                box.prop(self, "has_color")
                box.prop(self, "has_text")
                box.prop(self, "has_font")
                box.prop(self, "has_displaytype")
                box.prop(self, "has_alignment")
                box.prop(self, "has_kern")
                box.prop(self, "has_speed")
                box.prop(self, "has_size")
                box.prop(self, "has_alpha")
                box.prop(self, "has_fadeintime")
                box.prop(self, "has_fadeouttime")
                box.prop(self, "has_width")
                box.prop(self, "has_height")
                box.prop(self, "has_widthscale")
                box.prop(self, "has_id")
                box.prop(self, "has_active")
                box.prop(self, "has_node")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_offset: layout.prop(self, "offset")
            if self.has_color: layout.prop(self, "color")
            if self.has_text: layout.prop(self, "text")
            if self.has_font: layout.prop(self, "font")
            if self.has_displaytype: layout.prop(self, "displaytype")
            if self.has_alignment: layout.prop(self, "alignment")
            if self.has_kern: layout.prop(self, "kern")
            if self.has_speed: layout.prop(self, "speed")
            if self.has_size: layout.prop(self, "size")
            if self.has_alpha: layout.prop(self, "alpha")
            if self.has_fadeintime: layout.prop(self, "fadeintime")
            if self.has_fadeouttime: layout.prop(self, "fadeouttime")
            if self.has_width: layout.prop(self, "width")
            if self.has_height: layout.prop(self, "height")
            if self.has_widthscale: layout.prop(self, "widthscale")
            if self.has_id: layout.prop(self, "id")
            if self.has_active: layout.prop(self, "active")
            if self.has_node: layout.prop(self, "node")

        def generate(self, obj):
            tag = f"<textdisplay11 componentguid='{self.componentguid}' "
            if self.has_id: tag += f"id='{self.id}' "
            if self.has_active: tag += f"active='{self.active}' "
            if self.has_width: tag += f"width='{self.width}' "
            if self.has_height: tag += f"height='{self.height}' "
            if self.has_text: tag += f"text='{self.text}' "
            if self.has_font: tag += f"font='{self.font}' "
            if self.has_size: tag += f"size='{self.size}' "
            if self.has_widthscale: tag += f"widthscale='{self.widthscale}' "
            if self.has_kern: tag += f"kern='{self.kern}' "
            if self.has_speed: tag += f"speed='{self.speed}' "
            if self.has_color: tag += f"color='{self.color[0]},{self.color[1]},{self.color[2]}' "
            if self.has_alpha: tag += f"alpha='{self.alpha}' "
            if self.has_node: tag += f"node='{self.node}' "
            if self.has_offset: tag += f"offset='{self.offset[0]},{self.offset[1]},{self.offset[2]}' "
            if self.has_fadeintime: tag += f"fadeintime='{self.fadeintime}' "
            if self.has_fadeouttime: tag += f"fadeouttime='{self.fadeouttime}' "
            if self.has_displaytype: tag += f"displaytype='{self.displaytype}' "
            if self.has_alignment: tag += f"alignment='{self.alignment}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class TextDisplay12(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_offset: BoolProperty(name="Offset", description="",default=True)
        has_color: BoolProperty(name="Color", description="",default=True)
        has_text: BoolProperty(name="Text", description="",default=True)
        has_font: BoolProperty(name="Font", description="",default=True)
        has_displaytype: BoolProperty(name="Display Type", description="",default=True)
        has_alignment: BoolProperty(name="Alignment", description="",default=True)
        has_kern: BoolProperty(name="Kern", description="",default=False)
        has_speed: BoolProperty(name="Speed", description="",default=True)
        has_size: BoolProperty(name="Size", description="",default=True)
        has_alpha: BoolProperty(name="Alpha", description="",default=True)
        has_fadeintime: BoolProperty(name="Fade In Time", description="",default=True)
        has_fadeouttime: BoolProperty(name="Fade Out Time", description="",default=True)
        has_width: BoolProperty(name="Width", description="",default=True)
        has_height: BoolProperty(name="Height", description="",default=True)
        has_widthscale: BoolProperty(name="Width Scale", description="",default=False)
        has_id: BoolProperty(name="Id", description="",default=True)
        has_active: BoolProperty(name="Active", description="",default=True)
        has_node: BoolProperty(name="Node", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        id: EnumProperty(
            name="Id", description="",
            items=[
                ("","","Found in Tag Template"),
                ("spooce","spooce","Generated from Real Data"),
                ("display","display","Generated from Real Data")
            ]
        )

        active: BoolProperty(
            name="Active", description="",
            default=True
        )

        width: FloatProperty(
            name="Width", description="",
            default=72
        )

        height: FloatProperty(
            name="Height", description="",
            default=15
        )

        text: StringProperty(
            name="Text", description="",
            default=""
        )

        font: EnumProperty(
            name="Font", description="",
            items=[
    
                ("Main","Main","Generated default with script"),
                ("LED","LED","Generated from Real Data"),
                ("native","Native","Generated from Real Data"),
                ("inventory","Inventory","Found in TagTemplate"),
                ("newled","New LED","Found in TagTemplate"),
                
            ],
            default="Main"
        )

        size: FloatProperty(
            name="Size", description="",
            default=5
        )

        widthscale: FloatProperty(
            name="Width Scale", description="",
            default=1
        )

        kern: FloatProperty(
            name="Kern", description="",
            default=-1
        )

        speed: FloatProperty(
            name="Speed", description="",
            default=0
        )

        color: FloatVectorProperty(
            name="Color", description="",
            subtype="COLOR",
            min=0, max=1,
            default=(1,1,1)
        )

        alpha: FloatProperty(
            name="Alpha", description="",
            default=1
        )

        node: StringProperty(
            name="Node", description="",
            default="none"
        )

        offset: FloatVectorProperty(
            name="Offset", description="",
            subtype="XYZ",
            default=(0,0,0)
        )

        fadeintime: FloatProperty(
            name="Fade In Time", description="",
            default=0.4
        )

        fadeouttime: FloatProperty(
            name="Fade Out Time", description="",
            default=0.8
        )

        displaytype: EnumProperty(
            name="Display Type", description="",
            items=[
                ("scrolling","scrolling","Generated default with script"),
                ("floating","Floating","Generated from Real Data"),
                ("static","Static","Generated from Real Data"),
                ("rising","Rising","Generated from Real Data")
            ],
            default="scrolling"
        )

        alignment: EnumProperty(
            name="Alignment", description="",
            items=[
                ("left","left","Generated default with script"),
                ("center","Center","Generated from Real Data"),
                ("right","Right","Found in TagTemplate"),
            ],
            default="left"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Text Display 12")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_offset")
                box.prop(self, "has_color")
                box.prop(self, "has_text")
                box.prop(self, "has_font")
                box.prop(self, "has_displaytype")
                box.prop(self, "has_alignment")
                box.prop(self, "has_kern")
                box.prop(self, "has_speed")
                box.prop(self, "has_size")
                box.prop(self, "has_alpha")
                box.prop(self, "has_fadeintime")
                box.prop(self, "has_fadeouttime")
                box.prop(self, "has_width")
                box.prop(self, "has_height")
                box.prop(self, "has_widthscale")
                box.prop(self, "has_id")
                box.prop(self, "has_active")
                box.prop(self, "has_node")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_offset: layout.prop(self, "offset")
            if self.has_color: layout.prop(self, "color")
            if self.has_text: layout.prop(self, "text")
            if self.has_font: layout.prop(self, "font")
            if self.has_displaytype: layout.prop(self, "displaytype")
            if self.has_alignment: layout.prop(self, "alignment")
            if self.has_kern: layout.prop(self, "kern")
            if self.has_speed: layout.prop(self, "speed")
            if self.has_size: layout.prop(self, "size")
            if self.has_alpha: layout.prop(self, "alpha")
            if self.has_fadeintime: layout.prop(self, "fadeintime")
            if self.has_fadeouttime: layout.prop(self, "fadeouttime")
            if self.has_width: layout.prop(self, "width")
            if self.has_height: layout.prop(self, "height")
            if self.has_widthscale: layout.prop(self, "widthscale")
            if self.has_id: layout.prop(self, "id")
            if self.has_active: layout.prop(self, "active")
            if self.has_node: layout.prop(self, "node")

        def generate(self, obj):
            tag = f"<textdisplay12 componentguid='{self.componentguid}' "
            if self.has_id: tag += f"id='{self.id}' "
            if self.has_active: tag += f"active='{self.active}' "
            if self.has_width: tag += f"width='{self.width}' "
            if self.has_height: tag += f"height='{self.height}' "
            if self.has_text: tag += f"text='{self.text}' "
            if self.has_font: tag += f"font='{self.font}' "
            if self.has_size: tag += f"size='{self.size}' "
            if self.has_widthscale: tag += f"widthscale='{self.widthscale}' "
            if self.has_kern: tag += f"kern='{self.kern}' "
            if self.has_speed: tag += f"speed='{self.speed}' "
            if self.has_color: tag += f"color='{self.color[0]},{self.color[1]},{self.color[2]}' "
            if self.has_alpha: tag += f"alpha='{self.alpha}' "
            if self.has_node: tag += f"node='{self.node}' "
            if self.has_offset: tag += f"offset='{self.offset[0]},{self.offset[1]},{self.offset[2]}' "
            if self.has_fadeintime: tag += f"fadeintime='{self.fadeintime}' "
            if self.has_fadeouttime: tag += f"fadeouttime='{self.fadeouttime}' "
            if self.has_displaytype: tag += f"displaytype='{self.displaytype}' "
            if self.has_alignment: tag += f"alignment='{self.alignment}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag
    class TextDisplay13(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        has_offset: BoolProperty(name="Offset", description="",default=True)
        has_color: BoolProperty(name="Color", description="",default=True)
        has_text: BoolProperty(name="Text", description="",default=True)
        has_font: BoolProperty(name="Font", description="",default=True)
        has_displaytype: BoolProperty(name="Display Type", description="",default=True)
        has_alignment: BoolProperty(name="Alignment", description="",default=True)
        has_kern: BoolProperty(name="Kern", description="",default=False)
        has_speed: BoolProperty(name="Speed", description="",default=True)
        has_size: BoolProperty(name="Size", description="",default=True)
        has_alpha: BoolProperty(name="Alpha", description="",default=True)
        has_fadeintime: BoolProperty(name="Fade In Time", description="",default=True)
        has_fadeouttime: BoolProperty(name="Fade Out Time", description="",default=True)
        has_width: BoolProperty(name="Width", description="",default=True)
        has_height: BoolProperty(name="Height", description="",default=True)
        has_widthscale: BoolProperty(name="Width Scale", description="",default=False)
        has_id: BoolProperty(name="Id", description="",default=True)
        has_active: BoolProperty(name="Active", description="",default=True)
        has_node: BoolProperty(name="Node", description="",default=True)

        edit_componentguid: BoolProperty(name="Edit Component GUID", description="Reveal the edit field for the Component GUID for manually setting it",default=False)
        lock_componentguid: BoolProperty(
            name="Lock Component GUID",
            description="Prevents the Component GUID of this component from being overwritten when generating Component GUIDs",
            default=False
        )
        componentguid: IntProperty(
            name="Component GUID",
            description="The identifier of the component",
            default=-1
        )
        
        id: EnumProperty(
            name="Id", description="",
            items=[
                ("","","Found in Tag Template"),
                ("spooce","spooce","Generated from Real Data"),
                ("display","display","Generated from Real Data")
            ]
        )

        active: BoolProperty(
            name="Active", description="",
            default=True
        )

        width: FloatProperty(
            name="Width", description="",
            default=72
        )

        height: FloatProperty(
            name="Height", description="",
            default=15
        )

        text: StringProperty(
            name="Text", description="",
            default=""
        )

        font: EnumProperty(
            name="Font", description="",
            items=[
    
                ("Main","Main","Generated default with script"),
                ("LED","LED","Generated from Real Data"),
                ("native","Native","Generated from Real Data"),
                ("inventory","Inventory","Found in TagTemplate"),
                ("newled","New LED","Found in TagTemplate"),
                
            ],
            default="Main"
        )

        size: FloatProperty(
            name="Size", description="",
            default=5
        )

        widthscale: FloatProperty(
            name="Width Scale", description="",
            default=1
        )

        kern: FloatProperty(
            name="Kern", description="",
            default=-1
        )

        speed: FloatProperty(
            name="Speed", description="",
            default=0
        )

        color: FloatVectorProperty(
            name="Color", description="",
            subtype="COLOR",
            min=0, max=1,
            default=(1,1,1)
        )

        alpha: FloatProperty(
            name="Alpha", description="",
            default=1
        )

        node: StringProperty(
            name="Node", description="",
            default="none"
        )

        offset: FloatVectorProperty(
            name="Offset", description="",
            subtype="XYZ",
            default=(0,0,0)
        )

        fadeintime: FloatProperty(
            name="Fade In Time", description="",
            default=0.4
        )

        fadeouttime: FloatProperty(
            name="Fade Out Time", description="",
            default=0.8
        )

        displaytype: EnumProperty(
            name="Display Type", description="",
            items=[
                ("scrolling","scrolling","Generated default with script"),
                ("floating","Floating","Generated from Real Data"),
                ("static","Static","Generated from Real Data"),
                ("rising","Rising","Generated from Real Data")
            ],
            default="scrolling"
        )

        alignment: EnumProperty(
            name="Alignment", description="",
            items=[
                ("left","left","Generated default with script"),
                ("center","Center","Generated from Real Data"),
                ("right","Right","Found in TagTemplate"),
            ],
            default="left"
        )

        draw_show: BoolProperty(
            name="Show/Hide",
            default=False
        )
        
        def draw(self, layout):
            row = layout.row()
            row.label(text=f"[{self.componentguid}] Text Display 13")
            row.prop(self, "draw_show", toggle=1)
            if not self.draw_show: return
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_offset")
                box.prop(self, "has_color")
                box.prop(self, "has_text")
                box.prop(self, "has_font")
                box.prop(self, "has_displaytype")
                box.prop(self, "has_alignment")
                box.prop(self, "has_kern")
                box.prop(self, "has_speed")
                box.prop(self, "has_size")
                box.prop(self, "has_alpha")
                box.prop(self, "has_fadeintime")
                box.prop(self, "has_fadeouttime")
                box.prop(self, "has_width")
                box.prop(self, "has_height")
                box.prop(self, "has_widthscale")
                box.prop(self, "has_id")
                box.prop(self, "has_active")
                box.prop(self, "has_node")
            row = layout.row(align=True)
            row.prop(self, "edit_componentguid", toggle=1)            
            row.prop(self, "lock_componentguid", toggle=1)
            if self.edit_componentguid: layout.prop(self, "componentguid")  
            if self.has_offset: layout.prop(self, "offset")
            if self.has_color: layout.prop(self, "color")
            if self.has_text: layout.prop(self, "text")
            if self.has_font: layout.prop(self, "font")
            if self.has_displaytype: layout.prop(self, "displaytype")
            if self.has_alignment: layout.prop(self, "alignment")
            if self.has_kern: layout.prop(self, "kern")
            if self.has_speed: layout.prop(self, "speed")
            if self.has_size: layout.prop(self, "size")
            if self.has_alpha: layout.prop(self, "alpha")
            if self.has_fadeintime: layout.prop(self, "fadeintime")
            if self.has_fadeouttime: layout.prop(self, "fadeouttime")
            if self.has_width: layout.prop(self, "width")
            if self.has_height: layout.prop(self, "height")
            if self.has_widthscale: layout.prop(self, "widthscale")
            if self.has_id: layout.prop(self, "id")
            if self.has_active: layout.prop(self, "active")
            if self.has_node: layout.prop(self, "node")

        def generate(self, obj):
            tag = f"<textdisplay13 componentguid='{self.componentguid}' "
            if self.has_id: tag += f"id='{self.id}' "
            if self.has_active: tag += f"active='{self.active}' "
            if self.has_width: tag += f"width='{self.width}' "
            if self.has_height: tag += f"height='{self.height}' "
            if self.has_text: tag += f"text='{self.text}' "
            if self.has_font: tag += f"font='{self.font}' "
            if self.has_size: tag += f"size='{self.size}' "
            if self.has_widthscale: tag += f"widthscale='{self.widthscale}' "
            if self.has_kern: tag += f"kern='{self.kern}' "
            if self.has_speed: tag += f"speed='{self.speed}' "
            if self.has_color: tag += f"color='{self.color[0]},{self.color[1]},{self.color[2]}' "
            if self.has_alpha: tag += f"alpha='{self.alpha}' "
            if self.has_node: tag += f"node='{self.node}' "
            if self.has_offset: tag += f"offset='{self.offset[0]},{self.offset[1]},{self.offset[2]}' "
            if self.has_fadeintime: tag += f"fadeintime='{self.fadeintime}' "
            if self.has_fadeouttime: tag += f"fadeouttime='{self.fadeouttime}' "
            if self.has_displaytype: tag += f"displaytype='{self.displaytype}' "
            if self.has_alignment: tag += f"alignment='{self.alignment}' "
            tag += genTransform(obj)
            tag += "/>"
            return tag

    ### NEXT COMPONENT CLASS DEFINITION
    
    #GENERATED CLASSES END HERE
    
    def update_has_component(self, context):
        obj = context.object
        self.generate_component_guids(obj)
        update_mesh(context)
        pass

    def generate_component_guids(self, obj):
        cguid = 1
        if self.has_legmotion: 
            if not obj.XinComponentLegMotion.lock_componentguid:
                cguid += 1
                obj.XinComponentLegMotion.componentguid = cguid
        if self.has_flyingmotion: 
            if not obj.XinComponentFlyingMotion.lock_componentguid:
                cguid += 1
                obj.XinComponentFlyingMotion.componentguid = cguid
        if self.has_simplemotion: 
            if not obj.XinComponentSimpleMotion.lock_componentguid:
                cguid += 1
                obj.XinComponentSimpleMotion.componentguid = cguid
        if self.has_ear: 
            if not obj.XinComponentEar.lock_componentguid:
                cguid += 1
                obj.XinComponentEar.componentguid = cguid
        if self.has_munchanimation: 
            if not obj.XinComponentMunchAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentMunchAnimation.componentguid = cguid
        if self.has_mudokonanimation: 
            if not obj.XinComponentMudokonAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentMudokonAnimation.componentguid = cguid
        if self.has_simpleanimation: 
            if not obj.XinComponentSimpleAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentSimpleAnimation.componentguid = cguid
        if self.has_dooranimation: 
            if not obj.XinComponentDoorAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentDoorAnimation.componentguid = cguid
        if self.has_teleporteranimation: 
            if not obj.XinComponentTeleporterAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentTeleporterAnimation.componentguid = cguid
        if self.has_sliganimation: 
            if not obj.XinComponentSligAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentSligAnimation.componentguid = cguid
        if self.has_lever360animation: 
            if not obj.XinComponentLever360Animation.lock_componentguid:
                cguid += 1
                obj.XinComponentLever360Animation.componentguid = cguid
        if self.has_footswitchanimation: 
            if not obj.XinComponentFootSwitchAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentFootSwitchAnimation.componentguid = cguid
        if self.has_fuzzleanimation: 
            if not obj.XinComponentFuzzleAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentFuzzleAnimation.componentguid = cguid
        if self.has_vendingmachineanimation: 
            if not obj.XinComponentVendingMachineAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentVendingMachineAnimation.componentguid = cguid
        if self.has_bigbroanimation: 
            if not obj.XinComponentBigBroAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentBigBroAnimation.componentguid = cguid
        if self.has_nullanimation: 
            if not obj.XinComponentNullAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentNullAnimation.componentguid = cguid
        if self.has_glukkonanimation: 
            if not obj.XinComponentGlukkonAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentGlukkonAnimation.componentguid = cguid
        if self.has_wheelchairanimation: 
            if not obj.XinComponentWheelchairAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentWheelchairAnimation.componentguid = cguid
        if self.has_paramiteanimation: 
            if not obj.XinComponentParamiteAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentParamiteAnimation.componentguid = cguid
        if self.has_scrabanimation: 
            if not obj.XinComponentScrabAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentScrabAnimation.componentguid = cguid
        if self.has_genericparticlesanimation: 
            if not obj.XinComponentGenericParticlesAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentGenericParticlesAnimation.componentguid = cguid
        if self.has_meepanimation: 
            if not obj.XinComponentMeepAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentMeepAnimation.componentguid = cguid
        if self.has_internanimation: 
            if not obj.XinComponentInternAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentInternAnimation.componentguid = cguid
        if self.has_sloganimation: 
            if not obj.XinComponentSlogAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentSlogAnimation.componentguid = cguid
        if self.has_vykkeranimation: 
            if not obj.XinComponentVykkerAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentVykkerAnimation.componentguid = cguid
        if self.has_recycleranimation: 
            if not obj.XinComponentRecyclerAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentRecyclerAnimation.componentguid = cguid
        if self.has_candystriperanimation: 
            if not obj.XinComponentCandyStriperAnimation.lock_componentguid:
                cguid += 1
                obj.XinComponentCandyStriperAnimation.componentguid = cguid
        if self.has_behavior: 
            if not obj.XinComponentBehavior.lock_componentguid:
                cguid += 1
                obj.XinComponentBehavior.componentguid = cguid
        if self.has_job: 
            if not obj.XinComponentJob.lock_componentguid:
                cguid += 1
                obj.XinComponentJob.componentguid = cguid
        if self.has_doves: 
            if not obj.XinComponentDoves.lock_componentguid:
                cguid += 1
                obj.XinComponentDoves.componentguid = cguid
        if self.has_zapfx: 
            if not obj.XinComponentZapFx.lock_componentguid:
                cguid += 1
                obj.XinComponentZapFx.componentguid = cguid
        if self.has_assetlock: 
            if not obj.XinComponentAssetLock.lock_componentguid:
                cguid += 1
                obj.XinComponentAssetLock.componentguid = cguid
        if self.has_sparklestream: 
            if not obj.XinComponentSparkleStream.lock_componentguid:
                cguid += 1
                obj.XinComponentSparkleStream.componentguid = cguid
        if self.has_weapon: 
            if not obj.XinComponentWeapon.lock_componentguid:
                cguid += 1
                obj.XinComponentWeapon.componentguid = cguid
        if self.has_broadcaster: 
            if not obj.XinComponentBroadcaster.lock_componentguid:
                cguid += 1
                obj.XinComponentBroadcaster.componentguid = cguid
        if self.has_collectable: 
            if not obj.XinComponentCollectable.lock_componentguid:
                cguid += 1
                obj.XinComponentCollectable.componentguid = cguid
        if self.has_powerup: 
            if not obj.XinComponentPowerUp.lock_componentguid:
                cguid += 1
                obj.XinComponentPowerUp.componentguid = cguid
        if self.has_shadow: 
            if not obj.XinComponentShadow.lock_componentguid:
                cguid += 1
                obj.XinComponentShadow.componentguid = cguid
        if self.has_lifecycle: 
            if not obj.XinComponentLifeCycle.lock_componentguid:
                cguid += 1
                obj.XinComponentLifeCycle.componentguid = cguid
        if self.has_explosion: 
            if not obj.XinComponentExplosion.lock_componentguid:
                cguid += 1
                obj.XinComponentExplosion.componentguid = cguid
        if self.has_target: 
            if not obj.XinComponentTarget.lock_componentguid:
                cguid += 1
                obj.XinComponentTarget.componentguid = cguid
        if self.has_bullseye: 
            if not obj.XinComponentBullseye.lock_componentguid:
                cguid += 1
                obj.XinComponentBullseye.componentguid = cguid
        if self.has_shortgoal: 
            if not obj.XinComponentShortGoal.lock_componentguid:
                cguid += 1
                obj.XinComponentShortGoal.componentguid = cguid
        if self.has_transformer: 
            if not obj.XinComponentTransformer.lock_componentguid:
                cguid += 1
                obj.XinComponentTransformer.componentguid = cguid
        if self.has_onoffswitch: 
            if not obj.XinComponentOnOffSwitch.lock_componentguid:
                cguid += 1
                obj.XinComponentOnOffSwitch.componentguid = cguid
        if self.has_attachmentspawner: 
            if not obj.XinComponentAttachmentSpawner.lock_componentguid:
                cguid += 1
                obj.XinComponentAttachmentSpawner.componentguid = cguid
        if self.has_floatation: 
            if not obj.XinComponentFloatation.lock_componentguid:
                cguid += 1
                obj.XinComponentFloatation.componentguid = cguid
        if self.has_actortally: 
            if not obj.XinComponentActorTally.lock_componentguid:
                cguid += 1
                obj.XinComponentActorTally.componentguid = cguid
        if self.has_actortally2: 
            if not obj.XinComponentActorTally2.lock_componentguid:
                cguid += 1
                obj.XinComponentActorTally2.componentguid = cguid
        if self.has_actortally3: 
            if not obj.XinComponentActorTally3.lock_componentguid:
                cguid += 1
                obj.XinComponentActorTally3.componentguid = cguid
        if self.has_actortally4: 
            if not obj.XinComponentActorTally4.lock_componentguid:
                cguid += 1
                obj.XinComponentActorTally4.componentguid = cguid
        if self.has_actortally5: 
            if not obj.XinComponentActorTally5.lock_componentguid:
                cguid += 1
                obj.XinComponentActorTally5.componentguid = cguid
        if self.has_textdisplay: 
            if not obj.XinComponentTextDisplay.lock_componentguid:
                cguid += 1
                obj.XinComponentTextDisplay.componentguid = cguid
        if self.has_textdisplay2: 
            if not obj.XinComponentTextDisplay2.lock_componentguid:
                cguid += 1
                obj.XinComponentTextDisplay2.componentguid = cguid
        if self.has_textdisplay3: 
            if not obj.XinComponentTextDisplay3.lock_componentguid:
                cguid += 1
                obj.XinComponentTextDisplay3.componentguid = cguid
        if self.has_textdisplay4: 
            if not obj.XinComponentTextDisplay4.lock_componentguid:
                cguid += 1
                obj.XinComponentTextDisplay4.componentguid = cguid
        if self.has_textdisplay5: 
            if not obj.XinComponentTextDisplay5.lock_componentguid:
                cguid += 1
                obj.XinComponentTextDisplay5.componentguid = cguid
        if self.has_textdisplay6: 
            if not obj.XinComponentTextDisplay6.lock_componentguid:
                cguid += 1
                obj.XinComponentTextDisplay6.componentguid = cguid
        if self.has_textdisplay7: 
            if not obj.XinComponentTextDisplay7.lock_componentguid:
                cguid += 1
                obj.XinComponentTextDisplay7.componentguid = cguid
        if self.has_textdisplay8: 
            if not obj.XinComponentTextDisplay8.lock_componentguid:
                cguid += 1
                obj.XinComponentTextDisplay8.componentguid = cguid
        if self.has_textdisplay9: 
            if not obj.XinComponentTextDisplay9.lock_componentguid:
                cguid += 1
                obj.XinComponentTextDisplay9.componentguid = cguid
        if self.has_textdisplay10: 
            if not obj.XinComponentTextDisplay10.lock_componentguid:
                cguid += 1
                obj.XinComponentTextDisplay10.componentguid = cguid
        if self.has_textdisplay11: 
            if not obj.XinComponentTextDisplay11.lock_componentguid:
                cguid += 1
                obj.XinComponentTextDisplay11.componentguid = cguid
        if self.has_textdisplay12: 
            if not obj.XinComponentTextDisplay12.lock_componentguid:
                cguid += 1
                obj.XinComponentTextDisplay12.componentguid = cguid
        if self.has_textdisplay13: 
            if not obj.XinComponentTextDisplay13.lock_componentguid:
                cguid += 1
                obj.XinComponentTextDisplay13.componentguid = cguid
        pass
    
    showComponents :                BoolProperty(name="Show Components", description="Reveal the components of the Actor", default=False)
    showHasComponents :             BoolProperty(name="Add/Remove Components", description="Displays the list of components", default=False)    
    
    has_legmotion:                  BoolProperty(name="Leg Motion",description="",default=False, update=update_has_component)
    has_flyingmotion:               BoolProperty(name="Flying Motion",description="",default=False, update=update_has_component)
    has_simplemotion:               BoolProperty(name="Simple Motion",description="",default=False, update=update_has_component)
    has_ear:                        BoolProperty(name="Ear",description="",default=False, update=update_has_component)
    has_munchanimation:             BoolProperty(name="Munch Animation",description="",default=False, update=update_has_component)
    has_mudokonanimation:           BoolProperty(name="Mudokon Animation",description="",default=False, update=update_has_component)
    has_simpleanimation:            BoolProperty(name="Simple Animation",description="",default=False, update=update_has_component)
    has_dooranimation:              BoolProperty(name="Door Animation",description="",default=False, update=update_has_component)
    has_teleporteranimation:        BoolProperty(name="Teleporter Animation",description="",default=False, update=update_has_component)
    has_sliganimation:              BoolProperty(name="Slig Animation",description="",default=False, update=update_has_component)
    has_lever360animation:          BoolProperty(name="Lever 360 Animation",description="",default=False, update=update_has_component)
    has_footswitchanimation:        BoolProperty(name="Foot Switch Animation",description="",default=False, update=update_has_component)
    has_fuzzleanimation:            BoolProperty(name="Fuzzle Animation",description="",default=False, update=update_has_component)
    has_vendingmachineanimation:    BoolProperty(name="Vending Machine Animation",description="",default=False, update=update_has_component)
    has_bigbroanimation:            BoolProperty(name="Big Bro Animation",description="",default=False, update=update_has_component)
    has_nullanimation:              BoolProperty(name="Null Animation",description="",default=False, update=update_has_component)
    has_glukkonanimation:           BoolProperty(name="Glukkon Animation",description="",default=False, update=update_has_component)
    has_wheelchairanimation:        BoolProperty(name="Wheelchair Animation",description="",default=False, update=update_has_component)
    has_paramiteanimation:          BoolProperty(name="Paramite Animation",description="",default=False, update=update_has_component)
    has_scrabanimation:             BoolProperty(name="Scrab Animation",description="",default=False, update=update_has_component)
    has_genericparticlesanimation:  BoolProperty(name="Generic Particles Animation",description="",default=False, update=update_has_component)
    has_meepanimation:              BoolProperty(name="Meep Animation",description="",default=False, update=update_has_component)
    has_internanimation:            BoolProperty(name="Intern Animation",description="",default=False, update=update_has_component)
    has_sloganimation:              BoolProperty(name="Slog Animation",description="",default=False, update=update_has_component)
    has_vykkeranimation:            BoolProperty(name="Vykker Animation",description="",default=False, update=update_has_component)
    has_recycleranimation:          BoolProperty(name="Recycler Animation",description="",default=False, update=update_has_component)
    has_candystriperanimation:      BoolProperty(name="Candy Striper Animation",description="",default=False, update=update_has_component)
    has_behavior:                   BoolProperty(name="Behavior",description="",default=False, update=update_has_component)
    has_job:                        BoolProperty(name="Job",description="",default=False, update=update_has_component)
    has_doves:                      BoolProperty(name="Doves",description="",default=False, update=update_has_component)
    has_zapfx:                      BoolProperty(name="Zap Fx",description="",default=False, update=update_has_component)
    has_assetlock:                  BoolProperty(name="Asset Lock",description="",default=False, update=update_has_component)
    has_sparklestream:              BoolProperty(name="Sparkle Stream",description="",default=False, update=update_has_component)
    has_weapon:                     BoolProperty(name="Weapon",description="",default=False, update=update_has_component)
    has_broadcaster:                BoolProperty(name="Broadcaster",description="",default=False, update=update_has_component)
    has_collectable:                BoolProperty(name="Collectable",description="",default=False, update=update_has_component)
    has_powerup:                    BoolProperty(name="Power Up",description="",default=False, update=update_has_component)
    has_shadow:                     BoolProperty(name="Shadow",description="",default=False, update=update_has_component)
    has_lifecycle:                  BoolProperty(name="Life Cycle",description="",default=False, update=update_has_component)
    has_explosion:                  BoolProperty(name="Explosion",description="",default=False, update=update_has_component)
    has_target:                     BoolProperty(name="Target",description="",default=False, update=update_has_component)
    has_bullseye:                   BoolProperty(name="Bullseye",description="",default=False, update=update_has_component)
    has_shortgoal:                  BoolProperty(name="Short Goal",description="",default=False, update=update_has_component)
    has_transformer:                BoolProperty(name="Transformer",description="",default=False, update=update_has_component)
    has_onoffswitch:                BoolProperty(name="On Off Switch",description="",default=False, update=update_has_component)
    has_attachmentspawner:          BoolProperty(name="Attachment Spawner",description="",default=False, update=update_has_component)
    has_floatation:                 BoolProperty(name="Floatation",description="",default=False, update=update_has_component)
    has_actortally:                 BoolProperty(name="Actor Tally",description="",default=False, update=update_has_component)
    has_actortally2:                BoolProperty(name="Actor Tally 2",description="",default=False, update=update_has_component)
    has_actortally3:                BoolProperty(name="Actor Tally 3",description="",default=False, update=update_has_component)
    has_actortally4:                BoolProperty(name="Actor Tally 4",description="",default=False, update=update_has_component)
    has_actortally5:                BoolProperty(name="Actor Tally 5",description="",default=False, update=update_has_component)
    has_textdisplay:                BoolProperty(name="Text Display",description="",default=False, update=update_has_component)
    has_textdisplay2:               BoolProperty(name="Text Display 2",description="",default=False, update=update_has_component)
    has_textdisplay3:               BoolProperty(name="Text Display 3",description="",default=False, update=update_has_component)
    has_textdisplay4:               BoolProperty(name="Text Display 4",description="",default=False, update=update_has_component)
    has_textdisplay5:               BoolProperty(name="Text Display 5",description="",default=False, update=update_has_component)
    has_textdisplay6:               BoolProperty(name="Text Display 6",description="",default=False, update=update_has_component)
    has_textdisplay7:               BoolProperty(name="Text Display 7",description="",default=False, update=update_has_component)
    has_textdisplay8:               BoolProperty(name="Text Display 8",description="",default=False, update=update_has_component)
    has_textdisplay9:               BoolProperty(name="Text Display 9",description="",default=False, update=update_has_component)
    has_textdisplay10:              BoolProperty(name="Text Display 10",description="",default=False, update=update_has_component)
    has_textdisplay11:              BoolProperty(name="Text Display 11",description="",default=False, update=update_has_component)
    has_textdisplay12:              BoolProperty(name="Text Display 12",description="",default=False, update=update_has_component)
    has_textdisplay13:              BoolProperty(name="Text Display 13",description="",default=False, update=update_has_component)
    
    ### NEXT HAS COMPONENT PROP
    
    # show attributes
    show_attributes: BoolProperty(name="Show/Hide Attributes", description="Toggles the visibility of the attributes.", default=True)
    
    # attribute search box prop
    search_attribute: StringProperty(
        name="Filter", description="Search fot the component by name",
        default=""
    )
    
    # component search box prop
    search_component: StringProperty(
        name="Filter", description="Search fot the component by name",
        default=""
    )
    
    #Actor.draw
    def draw(self, layout: bpy.types.UILayout, obj: bpy.types.Object):
        layout.label(text=f"[{self.componentguid}] Actor")
        # Attributes
        layout.prop(self, "edit_componentguid", toggle=1)
        if self.edit_componentguid: layout.prop(self, "componentguid") 
        
        layout.separator()
        layout.prop(self, "type")
        if ("custom", "testall").__contains__(self.type) : layout.prop(self, "customName")
        search = ""
        layout.prop(self, "show_attributes", toggle=1)
        if self.show_attributes:
            #row = layout.row(align=True)
            layout.label(text="Attributes:")
            layout.prop(self, "search_attribute")
            layout.prop(self, "showHasAttr", toggle=1)
            if self.showHasAttr == True:
                search = self.search_attribute.strip().lower()
                box = layout.box()

                #if ( search == "" or search in "") box.prop(self, "has_flavor")
                if search == "" or search in "flavor": box.prop(self, "has_flavor")
                if search == "" or search in "camera focus": box.prop(self, "has_camerafocus")
                if search == "" or search in "player control": box.prop(self, "has_playercontrol")
                if search == "" or search in "abe": box.prop(self, "has_abe")
                if search == "" or search in "allegiance": box.prop(self, "has_allegiance")
                if search == "" or search in "asset component": box.prop(self, "has_assetcomponent")
                if search == "" or search in "dest camera": box.prop(self, "has_destcamera")
                if search == "" or search in "dest layout": box.prop(self, "has_destlayout")
                if search == "" or search in "dest teleporter": box.prop(self, "has_destteleporter")
                if search == "" or search in "collide type": box.prop(self, "has_collidetype")
                if search == "" or search in "pickup": box.prop(self, "has_pickup")
                if search == "" or search in "env file name": box.prop(self, "has_envfilename")
                if search == "" or search in "file name": box.prop(self, "has_filename")
                if search == "" or search in "healthy color": box.prop(self, "has_healthycolor")
                if search == "" or search in "unhealthy color": box.prop(self, "has_unhealthycolor")
                if search == "" or search in "spawn type": box.prop(self, "has_spawntype")
                if search == "" or search in "off delay": box.prop(self, "has_offdelay")
                if search == "" or search in "acceptance list": box.prop(self, "has_acceptancelist")
                if search == "" or search in "breed": box.prop(self, "has_breed")
                if search == "" or search in "delay": box.prop(self, "has_delay")
                if search == "" or search in "dest guid": box.prop(self, "has_destguid")
                if search == "" or search in "launch height": box.prop(self, "has_launchheight")
                if search == "" or search in "reject dest": box.prop(self, "has_rejectdest")
                if search == "" or search in "reject height": box.prop(self, "has_rejectheight")
                if search == "" or search in "state": box.prop(self, "has_state")
                if search == "" or search in "style": box.prop(self, "has_style")
                if search == "" or search in "switch to cam": box.prop(self, "has_switchtocam")
                if search == "" or search in "launch dest": box.prop(self, "has_launchdest")
                if search == "" or search in "actor fall": box.prop(self, "has_actorfall")
                if search == "" or search in "max active": box.prop(self, "has_maxactive")
                if search == "" or search in "max spawn": box.prop(self, "has_maxspawn")
                if search == "" or search in "spawn delay": box.prop(self, "has_spawndelay")
                if search == "" or search in "spawn list": box.prop(self, "has_spawnlist")
                if search == "" or search in "active": box.prop(self, "has_active")
                if search == "" or search in "min level": box.prop(self, "has_minlevel")
                if search == "" or search in "on delay": box.prop(self, "has_ondelay")
                if search == "" or search in "height": box.prop(self, "has_height")
                if search == "" or search in "length": box.prop(self, "has_length")
                if search == "" or search in "width": box.prop(self, "has_width")
                if search == "" or search in "ambient color": box.prop(self, "has_ambientcolor")
                if search == "" or search in "diffuse color": box.prop(self, "has_diffusecolor")
                if search == "" or search in "light shape": box.prop(self, "has_lightshape")
                if search == "" or search in "light type": box.prop(self, "has_lighttype")
                if search == "" or search in "radius": box.prop(self, "has_radius")
                if search == "" or search in "is ready": box.prop(self, "has_isready")
                if search == "" or search in "hot spot offset": box.prop(self, "has_hotspotoffset")
                if search == "" or search in "link component": box.prop(self, "has_linkcomponent")
                if search == "" or search in "lever type": box.prop(self, "has_levertype")
                if search == "" or search in "health": box.prop(self, "has_health")
                if search == "" or search in "moolah": box.prop(self, "has_moolah")
                if search == "" or search in "moolah max": box.prop(self, "has_moolahmax")
                if search == "" or search in "spooce ball": box.prop(self, "has_spooceball")
                if search == "" or search in "is touch activated": box.prop(self, "has_istouchactivated")
                if search == "" or search in "visible": box.prop(self, "has_visible")
                if search == "" or search in "on time": box.prop(self, "has_ontime")
                if search == "" or search in "asset amount": box.prop(self, "has_assetamount")
                if search == "" or search in "link component guid": box.prop(self, "has_linkcomponentguid")
                if search == "" or search in "multi display guid": box.prop(self, "has_multidisplayguid")
                if search == "" or search in "partial payment": box.prop(self, "has_partialpayment")
                if search == "" or search in "script": box.prop(self, "has_script")
                if search == "" or search in "spooce": box.prop(self, "has_spooce")
                if search == "" or search in "spooce max": box.prop(self, "has_spoocemax")
                if search == "" or search in "button radius": box.prop(self, "has_buttonradius")
                if search == "" or search in "chant radius": box.prop(self, "has_chantradius")
                if search == "" or search in "particle value": box.prop(self, "has_particlevalue")
                if search == "" or search in "shadow type": box.prop(self, "has_shadowtype")
                if search == "" or search in "percent level": box.prop(self, "has_percentlevel")
                if search == "" or search in "multi teleport": box.prop(self, "has_multiteleport")
                if search == "" or search in "activation": box.prop(self, "has_activation")
                if search == "" or search in "lensflare type": box.prop(self, "has_lensflaretype")
                if search == "" or search in "light direction": box.prop(self, "has_lightdirection")
                if search == "" or search in "x axis": box.prop(self, "has_xaxis")
                if search == "" or search in "y axis": box.prop(self, "has_yaxis")
                if search == "" or search in "z axis": box.prop(self, "has_zaxis")
                if search == "" or search in "kill if you have to": box.prop(self, "has_killifyouhaveto")
                if search == "" or search in "max alive or dead": box.prop(self, "has_maxaliveordead")
                if search == "" or search in "dead list": box.prop(self, "has_deadlist")
                if search == "" or search in "prototype guid": box.prop(self, "has_prototypeguid")
                if search == "" or search in "greet message": box.prop(self, "has_greetmsg")
                if search == "" or search in "not ready message": box.prop(self, "has_notreadymsg")
                if search == "" or search in "direction": box.prop(self, "has_direction")
                if search == "" or search in "min alpha": box.prop(self, "has_minalpha")
                if search == "" or search in "max alpha": box.prop(self, "has_maxalpha")
                if search == "" or search in "can climb": box.prop(self, "has_canclimb")
                if search == "" or search in "scale": box.prop(self, "has_scale")
                if search == "" or search in "x velocity": box.prop(self, "has_xvelocity")
                if search == "" or search in "y velocity": box.prop(self, "has_yvelocity")
                if search == "" or search in "attenuation": box.prop(self, "has_attenuation")
                if search == "" or search in "amplitude": box.prop(self, "has_amplitude")
                if search == "" or search in "frequency": box.prop(self, "has_frequency")
                if search == "" or search in "x offset": box.prop(self, "has_xoffset")
                if search == "" or search in "y offset": box.prop(self, "has_yoffset")
                if search == "" or search in "health max": box.prop(self, "has_healthmax")
                if search == "" or search in "shadow opacity": box.prop(self, "has_shadowopacity")
                if search == "" or search in "specular color": box.prop(self, "has_specularcolor")
                if search == "" or search in "force": box.prop(self, "has_force")
                if search == "" or search in "particles": box.prop(self, "has_particles")
                if search == "" or search in "size": box.prop(self, "has_size")
                if search == "" or search in "body": box.prop(self, "has_body")
                if search == "" or search in "err display guid": box.prop(self, "has_errdisplayguid")
                if search == "" or search in "low asset message": box.prop(self, "has_lowassetmsg")
                if search == "" or search in "particle offset": box.prop(self, "has_particleoffset")
                if search == "" or search in "error delay": box.prop(self, "has_errordelay")
                if search == "" or search in "exclusive": box.prop(self, "has_exclusive")
                if search == "" or search in "component link": box.prop(self, "has_componentlink")
                if search == "" or search in "rescue these flavors": box.prop(self, "has_rescuetheseflavors")
                if search == "" or search in "fade distance": box.prop(self, "has_fadedistance")
                if search == "" or search in "divisor": box.prop(self, "has_divisor")
                if search == "" or search in "amplitude1": box.prop(self, "has_amplitude1")
                if search == "" or search in "amplitude2": box.prop(self, "has_amplitude2")
                if search == "" or search in "counting order": box.prop(self, "has_countingorder")
                if search == "" or search in "drop point": box.prop(self, "has_droppoint")
                if search == "" or search in "turn off delay": box.prop(self, "has_turnoffdelay")
                if search == "" or search in "bp height": box.prop(self, "has_bpheight")
                if search == "" or search in "inverted": box.prop(self, "has_inverted")
        
            box = layout.box()
            if search == "" or search in "Flavor".strip().lower(): 
                if self.has_flavor: box.prop(self, "flavor")
            if search == "" or search in "Camera Focus".strip().lower(): 
                if self.has_camerafocus: box.prop(self, "camerafocus")
            if search == "" or search in "Player Control".strip().lower(): 
                if self.has_playercontrol: box.prop(self, "playercontrol")
            if search == "" or search in "Abe".strip().lower(): 
                if self.has_abe: box.prop(self, "abe")
            if search == "" or search in "Allegiance".strip().lower(): 
                if self.has_allegiance: box.prop(self, "allegiance")
            if search == "" or search in "Asset Component".strip().lower(): 
                if self.has_assetcomponent: box.prop(self, "assetcomponent")
            if search == "" or search in "Dest Camera".strip().lower(): 
                if self.has_destcamera: box.prop(self, "destcamera")
            if search == "" or search in "Dest Layout".strip().lower(): 
                if self.has_destlayout: box.prop(self, "destlayout")
            if search == "" or search in "Dest Teleporter".strip().lower(): 
                if self.has_destteleporter: box.prop(self, "destteleporter")
            if search == "" or search in "Collide Type".strip().lower(): 
                if self.has_collidetype: box.prop(self, "collidetype")
            if search == "" or search in "Pickup".strip().lower(): 
                if self.has_pickup: box.prop(self, "pickup")
            if search == "" or search in "Env File Name".strip().lower(): 
                if self.has_envfilename: box.prop(self, "envfilename")
            if search == "" or search in "File Name".strip().lower(): 
                if self.has_filename: box.prop(self, "filename")
            if search == "" or search in "Healthy Color".strip().lower(): 
                if self.has_healthycolor: box.prop(self, "healthycolor")
            if search == "" or search in "Unhealthy Color".strip().lower(): 
                if self.has_unhealthycolor: box.prop(self, "unhealthycolor")
            if search == "" or search in "Spawn Type".strip().lower(): 
                if self.has_spawntype: box.prop(self, "spawntype")
            if search == "" or search in "Off Delay".strip().lower(): 
                if self.has_offdelay: box.prop(self, "offdelay")
            if search == "" or search in "Acceptance List".strip().lower(): 
                if self.has_acceptancelist: 
                    self.acceptancelist.draw(box, "Acceptance List")
                    #box2 = box.box()
                    #box2.label(text="Acceptance List")
                    #box2.prop(self, "acceptancelist_count")
                    #col = box2.column(align=True)
                    #for item in self.acceptancelist:
                    #    item.draw(col)
                    #box.prop(self, "acceptancelist")
            if search == "" or search in "Breed".strip().lower(): 
                if self.has_breed: box.prop(self, "breed")
            if search == "" or search in "Delay".strip().lower(): 
                if self.has_delay: box.prop(self, "delay")
            if search == "" or search in "Dest GUID".strip().lower(): 
                if self.has_destguid: box.prop(self, "destguid")
            if search == "" or search in "Launch Height".strip().lower(): 
                if self.has_launchheight: box.prop(self, "launchheight")
            if search == "" or search in "Reject Dest".strip().lower(): 
                if self.has_rejectdest: box.prop(self, "rejectdest")
            if search == "" or search in "Reject Height".strip().lower(): 
                if self.has_rejectheight: box.prop(self, "rejectheight")
            if search == "" or search in "State".strip().lower(): 
                if self.has_state: box.prop(self, "state")
            if search == "" or search in "Style".strip().lower(): 
                if self.has_style: box.prop(self, "style")
            if search == "" or search in "Switch To Cam".strip().lower(): 
                if self.has_switchtocam: box.prop(self, "switchtocam")
            if search == "" or search in "Launch Dest".strip().lower(): 
                if self.has_launchdest: box.prop(self, "launchdest")
            if search == "" or search in "Actor Fall".strip().lower(): 
                if self.has_actorfall: box.prop(self, "actorfall")
            if search == "" or search in "Max Active".strip().lower(): 
                if self.has_maxactive: box.prop(self, "maxactive")
            if search == "" or search in "Max Spawn".strip().lower(): 
                if self.has_maxspawn: box.prop(self, "maxspawn")
            if search == "" or search in "Spawn Delay".strip().lower(): 
                if self.has_spawndelay: box.prop(self, "spawndelay")
            if search == "" or search in "Spawn List".strip().lower(): 
                if self.has_spawnlist: self.spawnlist.draw(box, "Spawn List")
            if search == "" or search in "Active".strip().lower(): 
                if self.has_active: box.prop(self, "active")
            if search == "" or search in "Min Level".strip().lower(): 
                if self.has_minlevel: box.prop(self, "minlevel")
            if search == "" or search in "On Delay".strip().lower(): 
                if self.has_ondelay: box.prop(self, "ondelay")
            if search == "" or search in "Height".strip().lower(): 
                if self.has_height: box.prop(self, "height")
            if search == "" or search in "Length".strip().lower(): 
                if self.has_length: box.prop(self, "length")
            if search == "" or search in "Width".strip().lower(): 
                if self.has_width: box.prop(self, "width")
            if search == "" or search in "Ambient Color".strip().lower(): 
                if self.has_ambientcolor: box.prop(self, "ambientcolor")
            if search == "" or search in "Diffuse Color".strip().lower(): 
                if self.has_diffusecolor: box.prop(self, "diffusecolor")
            if search == "" or search in "Light Shape".strip().lower(): 
                if self.has_lightshape: box.prop(self, "lightshape")
            if search == "" or search in "Light Type".strip().lower(): 
                if self.has_lighttype: box.prop(self, "lighttype")
            if search == "" or search in "Radius".strip().lower(): 
                if self.has_radius: box.prop(self, "radius")
            if search == "" or search in "Is Ready".strip().lower(): 
                if self.has_isready: box.prop(self, "isready")
            if search == "" or search in "Hot Spot Offset".strip().lower(): 
                if self.has_hotspotoffset: box.prop(self, "hotspotoffset")
            if search == "" or search in "Link Component".strip().lower(): 
                if self.has_linkcomponent: box.prop(self, "linkcomponent")
            if search == "" or search in "Lever Type".strip().lower(): 
                if self.has_levertype: box.prop(self, "levertype")
            if search == "" or search in "Health".strip().lower(): 
                if self.has_health: box.prop(self, "health")
            if search == "" or search in "Moolah".strip().lower(): 
                if self.has_moolah: box.prop(self, "moolah")
            if search == "" or search in "Moolah Max".strip().lower(): 
                if self.has_moolahmax: box.prop(self, "moolahmax")
            if search == "" or search in "Spooce Ball".strip().lower(): 
                if self.has_spooceball: box.prop(self, "spooceball")
            if search == "" or search in "Is Touch Activated".strip().lower(): 
                if self.has_istouchactivated: box.prop(self, "istouchactivated")
            if search == "" or search in "Visible".strip().lower(): 
                if self.has_visible: box.prop(self, "visible")
            if search == "" or search in "On Time".strip().lower(): 
                if self.has_ontime: box.prop(self, "ontime")
            if search == "" or search in "Asset Amount".strip().lower(): 
                if self.has_assetamount: box.prop(self, "assetamount")
            if search == "" or search in "Link Component GUID".strip().lower(): 
                if self.has_linkcomponentguid: box.prop(self, "linkcomponentguid")
            if search == "" or search in "Multi Display GUID".strip().lower(): 
                if self.has_multidisplayguid: box.prop(self, "multidisplayguid")
            if search == "" or search in "Partial Payment".strip().lower(): 
                if self.has_partialpayment: box.prop(self, "partialpayment")
            if search == "" or search in "Script".strip().lower(): 
                if self.has_script: box.prop(self, "script")
            if search == "" or search in "Spooce".strip().lower(): 
                if self.has_spooce: box.prop(self, "spooce")
            if search == "" or search in "Spooce Max".strip().lower(): 
                if self.has_spoocemax: box.prop(self, "spoocemax")
            if search == "" or search in "Button Radius".strip().lower(): 
                if self.has_buttonradius: box.prop(self, "buttonradius")
            if search == "" or search in "Chant Radius".strip().lower(): 
                if self.has_chantradius: box.prop(self, "chantradius")
            if search == "" or search in "Particle Value".strip().lower(): 
                if self.has_particlevalue: box.prop(self, "particlevalue")
            if search == "" or search in "Shadow Type".strip().lower(): 
                if self.has_shadowtype: box.prop(self, "shadowtype")
            if search == "" or search in "Percent Level".strip().lower(): 
                if self.has_percentlevel: box.prop(self, "percentlevel")
            if search == "" or search in "Multi Teleport".strip().lower(): 
                if self.has_multiteleport: box.prop(self, "multiteleport")
            if search == "" or search in "Activation".strip().lower(): 
                if self.has_activation: box.prop(self, "activation")
            if search == "" or search in "Lensflare Type".strip().lower(): 
                if self.has_lensflaretype: box.prop(self, "lensflaretype")
            if search == "" or search in "Light Direction".strip().lower(): 
                if self.has_lightdirection: box.prop(self, "lightdirection")
            if search == "" or search in "X Axis".strip().lower(): 
                if self.has_xaxis: box.prop(self, "xaxis")
            if search == "" or search in "Y Axis".strip().lower(): 
                if self.has_yaxis: box.prop(self, "yaxis")
            if search == "" or search in "Z Axis".strip().lower(): 
                if self.has_zaxis: box.prop(self, "zaxis")
            if search == "" or search in "Kill If You Have To".strip().lower(): 
                if self.has_killifyouhaveto: box.prop(self, "killifyouhaveto")
            if search == "" or search in "Max Alive Or Dead".strip().lower(): 
                if self.has_maxaliveordead: box.prop(self, "maxaliveordead")
            if search == "" or search in "Dead List".strip().lower(): 
                if self.has_deadlist: 
                    self.deadlist.draw(box, "Dead List")
                    #box2 = box.box()
                    #box2.label(text="Dead List")
                    #box2.prop(self, "deadlist_count")
                    #col = box2.column(align=True)
                    #for item in self.deadlist:
                    #    item.draw(col)
            if search == "" or search in "Prototype GUID".strip().lower(): 
                if self.has_prototypeguid: box.prop(self, "prototypeguid")
            if search == "" or search in "Greet Message".strip().lower(): 
                if self.has_greetmsg: box.prop(self, "greetmsg")
            if search == "" or search in "Not Ready Message".strip().lower(): 
                if self.has_notreadymsg: box.prop(self, "notreadymsg")
            if search == "" or search in "Direction".strip().lower(): 
                if self.has_direction: box.prop(self, "direction")
            if search == "" or search in "Min Alpha".strip().lower(): 
                if self.has_minalpha: box.prop(self, "minalpha")
            if search == "" or search in "Max Alpha".strip().lower(): 
                if self.has_maxalpha: box.prop(self, "maxalpha")
            if search == "" or search in "Can Climb".strip().lower(): 
                if self.has_canclimb: box.prop(self, "canclimb")
            if search == "" or search in "Scale".strip().lower(): 
                if self.has_scale: box.prop(self, "scale")
            if search == "" or search in "X Velocity".strip().lower(): 
                if self.has_xvelocity: box.prop(self, "xvelocity")
            if search == "" or search in "Y Velocity".strip().lower(): 
                if self.has_yvelocity: box.prop(self, "yvelocity")
            if search == "" or search in "Attenuation".strip().lower(): 
                if self.has_attenuation: box.prop(self, "attenuation")
            if search == "" or search in "Amplitude".strip().lower(): 
                if self.has_amplitude: box.prop(self, "amplitude")
            if search == "" or search in "Frequency".strip().lower(): 
                if self.has_frequency: box.prop(self, "frequency")
            if search == "" or search in "X Offset".strip().lower(): 
                if self.has_xoffset: box.prop(self, "xoffset")
            if search == "" or search in "Y Offset".strip().lower(): 
                if self.has_yoffset: box.prop(self, "yoffset")
            if search == "" or search in "Health Max".strip().lower(): 
                if self.has_healthmax: box.prop(self, "healthmax")
            if search == "" or search in "Shadow Opacity".strip().lower(): 
                if self.has_shadowopacity: box.prop(self, "shadowopacity")
            if search == "" or search in "Specular Color".strip().lower(): 
                if self.has_specularcolor: box.prop(self, "specularcolor")
            if search == "" or search in "Force".strip().lower(): 
                if self.has_force: box.prop(self, "force")
            if search == "" or search in "Particles".strip().lower(): 
                if self.has_particles: box.prop(self, "particles")
            if search == "" or search in "Size".strip().lower(): 
                if self.has_size: box.prop(self, "size")
            if search == "" or search in "Body".strip().lower(): 
                if self.has_body: box.prop(self, "body")
            if search == "" or search in "Err Display GUID".strip().lower(): 
                if self.has_errdisplayguid: box.prop(self, "errdisplayguid")
            if search == "" or search in "Low Asset Message".strip().lower(): 
                if self.has_lowassetmsg: box.prop(self, "lowassetmsg")
            if search == "" or search in "Particle Offset".strip().lower(): 
                if self.has_particleoffset: box.prop(self, "particleoffset")
            if search == "" or search in "Error Delay".strip().lower(): 
                if self.has_errordelay: box.prop(self, "errordelay")
            if search == "" or search in "Exclusive".strip().lower(): 
                if self.has_exclusive: box.prop(self, "exclusive")
            if search == "" or search in "Component Link".strip().lower(): 
                if self.has_componentlink: box.prop(self, "componentlink")
            if search == "" or search in "Rescue These Flavors".strip().lower(): 
                if self.has_rescuetheseflavors: box.prop(self, "rescuetheseflavors")
            if search == "" or search in "Fade Distance".strip().lower(): 
                if self.has_fadedistance: box.prop(self, "fadedistance")
            if search == "" or search in "Divisor".strip().lower(): 
                if self.has_divisor: box.prop(self, "divisor")
            if search == "" or search in "Amplitude1".strip().lower(): 
                if self.has_amplitude1: box.prop(self, "amplitude1")
            if search == "" or search in "Amplitude2".strip().lower(): 
                if self.has_amplitude2: box.prop(self, "amplitude2")
            if search == "" or search in "Counting Order".strip().lower(): 
                if self.has_countingorder: box.prop(self, "countingorder")
            if search == "" or search in "Drop Point".strip().lower(): 
                if self.has_droppoint: box.prop(self, "droppoint")
            if search == "" or search in "Turn Off Delay".strip().lower(): 
                if self.has_turnoffdelay: box.prop(self, "turnoffdelay")
            if search == "" or search in "BP Height".strip().lower(): 
                if self.has_bpheight: box.prop(self, "bpheight")
            if search == "" or search in "Inverted".strip().lower(): 
                if self.has_inverted: box.prop(self, "inverted")
        
        cguid = 1
        
        #Components
        #layout.separator()
        layout.prop(self, "showComponents", toggle=1)
        if self.showComponents == True:
            row = layout.row()
            layout.label(text="Components:")
            layout.prop(self, "search_component")
            search = self.search_component.strip().lower()

            layout.prop(self, "showHasComponents", toggle=1)
            if self.showHasComponents == True:
                box = layout.box()
                if search == "" or search in "Leg Motion".strip().lower(): box.prop(self, "has_legmotion")
                if search == "" or search in "Flying Motion".strip().lower(): box.prop(self, "has_flyingmotion")
                if search == "" or search in "Simple Motion".strip().lower(): box.prop(self, "has_simplemotion")
                if search == "" or search in "Ear".strip().lower(): box.prop(self, "has_ear")
                if search == "" or search in "Munch Animation".strip().lower(): box.prop(self, "has_munchanimation")
                if search == "" or search in "Mudokon Animation".strip().lower(): box.prop(self, "has_mudokonanimation")
                if search == "" or search in "Simple Animation".strip().lower(): box.prop(self, "has_simpleanimation")
                if search == "" or search in "Door Animation".strip().lower(): box.prop(self, "has_dooranimation")
                if search == "" or search in "Teleporter Animation".strip().lower(): box.prop(self, "has_teleporteranimation")
                if search == "" or search in "Slig Animation".strip().lower(): box.prop(self, "has_sliganimation")
                if search == "" or search in "Lever 360 Animation".strip().lower(): box.prop(self, "has_lever360animation")
                if search == "" or search in "Foot Switch Animation".strip().lower(): box.prop(self, "has_footswitchanimation")
                if search == "" or search in "Fuzzle Animation".strip().lower(): box.prop(self, "has_fuzzleanimation")
                if search == "" or search in "Vending Machine Animation".strip().lower(): box.prop(self, "has_vendingmachineanimation")
                if search == "" or search in "Big Bro Animation".strip().lower(): box.prop(self, "has_bigbroanimation")
                if search == "" or search in "Null Animation".strip().lower(): box.prop(self, "has_nullanimation")
                if search == "" or search in "Glukkon Animation".strip().lower(): box.prop(self, "has_glukkonanimation")
                if search == "" or search in "Wheelchair Animation".strip().lower(): box.prop(self, "has_wheelchairanimation")
                if search == "" or search in "Paramite Animation".strip().lower(): box.prop(self, "has_paramiteanimation")
                if search == "" or search in "Scrab Animation".strip().lower(): box.prop(self, "has_scrabanimation")
                if search == "" or search in "Generic Particles Animation".strip().lower(): box.prop(self, "has_genericparticlesanimation")
                if search == "" or search in "Meep Animation".strip().lower(): box.prop(self, "has_meepanimation")
                if search == "" or search in "Intern Animation".strip().lower(): box.prop(self, "has_internanimation")
                if search == "" or search in "Slog Animation".strip().lower(): box.prop(self, "has_sloganimation")
                if search == "" or search in "Vykker Animation".strip().lower(): box.prop(self, "has_vykkeranimation")
                if search == "" or search in "Recycler Animation".strip().lower(): box.prop(self, "has_recycleranimation")
                if search == "" or search in "Candy Striper Animation".strip().lower(): box.prop(self, "has_candystriperanimation")
                if search == "" or search in "Behavior".strip().lower(): box.prop(self, "has_behavior")
                if search == "" or search in "Job".strip().lower(): box.prop(self, "has_job")
                if search == "" or search in "Doves".strip().lower(): box.prop(self, "has_doves")
                if search == "" or search in "Zap Fx".strip().lower(): box.prop(self, "has_zapfx")
                if search == "" or search in "Asset Lock".strip().lower(): box.prop(self, "has_assetlock")
                if search == "" or search in "Sparkle Stream".strip().lower(): box.prop(self, "has_sparklestream")
                if search == "" or search in "Weapon".strip().lower(): box.prop(self, "has_weapon")
                if search == "" or search in "Broadcaster".strip().lower(): box.prop(self, "has_broadcaster")
                if search == "" or search in "Collectable".strip().lower(): box.prop(self, "has_collectable")
                if search == "" or search in "Power Up".strip().lower(): box.prop(self, "has_powerup")
                if search == "" or search in "Shadow".strip().lower(): box.prop(self, "has_shadow")
                if search == "" or search in "Life Cycle".strip().lower(): box.prop(self, "has_lifecycle")
                if search == "" or search in "Explosion".strip().lower(): box.prop(self, "has_explosion")
                if search == "" or search in "Target".strip().lower(): box.prop(self, "has_target")
                if search == "" or search in "Bullseye".strip().lower(): box.prop(self, "has_bullseye")
                if search == "" or search in "Short Goal".strip().lower(): box.prop(self, "has_shortgoal")
                if search == "" or search in "Transformer".strip().lower(): box.prop(self, "has_transformer")
                if search == "" or search in "On Off Switch".strip().lower(): box.prop(self, "has_onoffswitch")
                if search == "" or search in "Attachment Spawner".strip().lower(): box.prop(self, "has_attachmentspawner")
                if search == "" or search in "Floatation".strip().lower(): box.prop(self, "has_floatation")
                if search == "" or search in "Actor Tally".strip().lower(): box.prop(self, "has_actortally")
                if search == "" or search in "Actor Tally 2".strip().lower(): box.prop(self, "has_actortally2")
                if search == "" or search in "Actor Tally 3".strip().lower(): box.prop(self, "has_actortally3")
                if search == "" or search in "Actor Tally 4".strip().lower(): box.prop(self, "has_actortally4")
                if search == "" or search in "Actor Tally 5".strip().lower(): box.prop(self, "has_actortally5")
                if search == "" or search in "Text Display".strip().lower(): box.prop(self, "has_textdisplay")
                if search == "" or search in "Text Display 2".strip().lower(): box.prop(self, "has_textdisplay2")
                if search == "" or search in "Text Display 3".strip().lower(): box.prop(self, "has_textdisplay3")
                if search == "" or search in "Text Display 4".strip().lower(): box.prop(self, "has_textdisplay4")
                if search == "" or search in "Text Display 5".strip().lower(): box.prop(self, "has_textdisplay5")
                if search == "" or search in "Text Display 6".strip().lower(): box.prop(self, "has_textdisplay6")
                if search == "" or search in "Text Display 7".strip().lower(): box.prop(self, "has_textdisplay7")
                if search == "" or search in "Text Display 8".strip().lower(): box.prop(self, "has_textdisplay8")
                if search == "" or search in "Text Display 9".strip().lower(): box.prop(self, "has_textdisplay9")
                if search == "" or search in "Text Display 10".strip().lower(): box.prop(self, "has_textdisplay10")
                if search == "" or search in "Text Display 11".strip().lower(): box.prop(self, "has_textdisplay11")
                if search == "" or search in "Text Display 12".strip().lower(): box.prop(self, "has_textdisplay12")
                if search == "" or search in "Text Display 13".strip().lower(): box.prop(self, "has_textdisplay13")
                ### NEXT BOX PROP IN ACTOR DRAW

            if search == "" or search in "Leg Motion".strip().lower(): 
                if self.has_legmotion:
                    obj.XinComponentLegMotion.draw(layout.box())
            if search == "" or search in "Flying Motion".strip().lower(): 
                if self.has_flyingmotion:
                    obj.XinComponentFlyingMotion.draw(layout.box())
            if search == "" or search in "Simple Motion".strip().lower(): 
                if self.has_simplemotion:
                    obj.XinComponentSimpleMotion.draw(layout.box())
            if search == "" or search in "Ear".strip().lower(): 
                if self.has_ear:
                    obj.XinComponentEar.draw(layout.box())
            if search == "" or search in "Munch Animation".strip().lower(): 
                if self.has_munchanimation:
                    obj.XinComponentMunchAnimation.draw(layout.box())
            if search == "" or search in "Mudokon Animation".strip().lower(): 
                if self.has_mudokonanimation:
                    obj.XinComponentMudokonAnimation.draw(layout.box())
            if search == "" or search in "Simple Animation".strip().lower(): 
                if self.has_simpleanimation:
                    obj.XinComponentSimpleAnimation.draw(layout.box())
            if search == "" or search in "Door Animation".strip().lower(): 
                if self.has_dooranimation:
                    obj.XinComponentDoorAnimation.draw(layout.box())
            if search == "" or search in "Teleporter Animation".strip().lower(): 
                if self.has_teleporteranimation:
                    obj.XinComponentTeleporterAnimation.draw(layout.box())
            if search == "" or search in "Slig Animation".strip().lower(): 
                if self.has_sliganimation:
                    obj.XinComponentSligAnimation.draw(layout.box())
            if search == "" or search in "Lever 360 Animation".strip().lower(): 
                if self.has_lever360animation:
                    obj.XinComponentLever360Animation.draw(layout.box())
            if search == "" or search in "Foot Switch Animation".strip().lower(): 
                if self.has_footswitchanimation:
                    obj.XinComponentFootSwitchAnimation.draw(layout.box())
            if search == "" or search in "Fuzzle Animation".strip().lower(): 
                if self.has_fuzzleanimation:
                    obj.XinComponentFuzzleAnimation.draw(layout.box())
            if search == "" or search in "Vending Machine Animation".strip().lower(): 
                if self.has_vendingmachineanimation:
                    obj.XinComponentVendingMachineAnimation.draw(layout.box())
            if search == "" or search in "Big Bro Animation".strip().lower(): 
                if self.has_bigbroanimation:
                    obj.XinComponentBigBroAnimation.draw(layout.box())
            if search == "" or search in "Null Animation".strip().lower(): 
                if self.has_nullanimation:
                    obj.XinComponentNullAnimation.draw(layout.box())
            if search == "" or search in "Glukkon Animation".strip().lower(): 
                if self.has_glukkonanimation:
                    obj.XinComponentGlukkonAnimation.draw(layout.box())
            if search == "" or search in "Wheelchair Animation".strip().lower(): 
                if self.has_wheelchairanimation:
                    obj.XinComponentWheelchairAnimation.draw(layout.box())
            if search == "" or search in "Paramite Animation".strip().lower(): 
                if self.has_paramiteanimation:
                    obj.XinComponentParamiteAnimation.draw(layout.box())
            if search == "" or search in "Scrab Animation".strip().lower(): 
                if self.has_scrabanimation:
                    obj.XinComponentScrabAnimation.draw(layout.box())
            if search == "" or search in "Generic Particles Animation".strip().lower(): 
                if self.has_genericparticlesanimation:
                    obj.XinComponentGenericParticlesAnimation.draw(layout.box())
            if search == "" or search in "Meep Animation".strip().lower(): 
                if self.has_meepanimation:
                    obj.XinComponentMeepAnimation.draw(layout.box())
            if search == "" or search in "Intern Animation".strip().lower(): 
                if self.has_internanimation:
                    obj.XinComponentInternAnimation.draw(layout.box())
            if search == "" or search in "Slog Animation".strip().lower(): 
                if self.has_sloganimation:
                    obj.XinComponentSlogAnimation.draw(layout.box())
            if search == "" or search in "Vykker Animation".strip().lower(): 
                if self.has_vykkeranimation:
                    obj.XinComponentVykkerAnimation.draw(layout.box())
            if search == "" or search in "Recycler Animation".strip().lower(): 
                if self.has_recycleranimation:
                    obj.XinComponentRecyclerAnimation.draw(layout.box())
            if search == "" or search in "Candy Striper Animation".strip().lower(): 
                if self.has_candystriperanimation:
                    obj.XinComponentCandyStriperAnimation.draw(layout.box())
            if search == "" or search in "Behavior".strip().lower(): 
                if self.has_behavior:
                    obj.XinComponentBehavior.draw(layout.box())
            if search == "" or search in "Job".strip().lower(): 
                if self.has_job:
                    obj.XinComponentJob.draw(layout.box())
            if search == "" or search in "Doves".strip().lower(): 
                if self.has_doves:
                    obj.XinComponentDoves.draw(layout.box())
            if search == "" or search in "Zap Fx".strip().lower(): 
                if self.has_zapfx:
                    obj.XinComponentZapFx.draw(layout.box())
            if search == "" or search in "Asset Lock".strip().lower(): 
                if self.has_assetlock:
                    obj.XinComponentAssetLock.draw(layout.box())
            if search == "" or search in "Sparkle Stream".strip().lower(): 
                if self.has_sparklestream:
                    obj.XinComponentSparkleStream.draw(layout.box())
            if search == "" or search in "Weapon".strip().lower(): 
                if self.has_weapon:
                    obj.XinComponentWeapon.draw(layout.box())
            if search == "" or search in "Broadcaster".strip().lower(): 
                if self.has_broadcaster:
                    obj.XinComponentBroadcaster.draw(layout.box())
            if search == "" or search in "Collectable".strip().lower(): 
                if self.has_collectable:
                    obj.XinComponentCollectable.draw(layout.box())
            if search == "" or search in "Power Up".strip().lower(): 
                if self.has_powerup:
                    obj.XinComponentPowerUp.draw(layout.box())
            if search == "" or search in "Shadow".strip().lower(): 
                if self.has_shadow:
                    obj.XinComponentShadow.draw(layout.box())
            if search == "" or search in "Life Cycle".strip().lower(): 
                if self.has_lifecycle:
                    obj.XinComponentLifeCycle.draw(layout.box())
            if search == "" or search in "Explosion".strip().lower(): 
                if self.has_explosion:
                    obj.XinComponentExplosion.draw(layout.box())
            if search == "" or search in "Target".strip().lower(): 
                if self.has_target:
                    obj.XinComponentTarget.draw(layout.box())
            if search == "" or search in "Bullseye".strip().lower(): 
                if self.has_bullseye:
                    obj.XinComponentBullseye.draw(layout.box())
            if search == "" or search in "Short Goal".strip().lower(): 
                if self.has_shortgoal:
                    obj.XinComponentShortGoal.draw(layout.box())
            if search == "" or search in "Transformer".strip().lower(): 
                if self.has_transformer:
                    obj.XinComponentTransformer.draw(layout.box())
            if search == "" or search in "On Off Switch".strip().lower(): 
                if self.has_onoffswitch:
                    obj.XinComponentOnOffSwitch.draw(layout.box())
            if search == "" or search in "Attachment Spawner".strip().lower(): 
                if self.has_attachmentspawner:
                    obj.XinComponentAttachmentSpawner.draw(layout.box())
            if search == "" or search in "Floatation".strip().lower(): 
                if self.has_floatation:
                    obj.XinComponentFloatation.draw(layout.box())
            if search == "" or search in "Actor Tally".strip().lower(): 
                if self.has_actortally:
                    obj.XinComponentActorTally.draw(layout.box())
            if search == "" or search in "Actor Tally 2".strip().lower(): 
                if self.has_actortally2:
                    obj.XinComponentActorTally2.draw(layout.box())
            if search == "" or search in "Actor Tally 3".strip().lower(): 
                if self.has_actortally3:
                    obj.XinComponentActorTally3.draw(layout.box())
            if search == "" or search in "Actor Tally 4".strip().lower(): 
                if self.has_actortally4:
                    obj.XinComponentActorTally4.draw(layout.box())
            if search == "" or search in "Actor Tally 5".strip().lower(): 
                if self.has_actortally5:
                    obj.XinComponentActorTally5.draw(layout.box())
            if search == "" or search in "Text Display".strip().lower(): 
                if self.has_textdisplay:
                    obj.XinComponentTextDisplay.draw(layout.box())
            if search == "" or search in "Text Display 2".strip().lower(): 
                if self.has_textdisplay2:
                    obj.XinComponentTextDisplay2.draw(layout.box())
            if search == "" or search in "Text Display 3".strip().lower(): 
                if self.has_textdisplay3:
                    obj.XinComponentTextDisplay3.draw(layout.box())
            if search == "" or search in "Text Display 4".strip().lower(): 
                if self.has_textdisplay4:
                    obj.XinComponentTextDisplay4.draw(layout.box())
            if search == "" or search in "Text Display 5".strip().lower(): 
                if self.has_textdisplay5:
                    obj.XinComponentTextDisplay5.draw(layout.box())
            if search == "" or search in "Text Display 6".strip().lower(): 
                if self.has_textdisplay6:
                    obj.XinComponentTextDisplay6.draw(layout.box())
            if search == "" or search in "Text Display 7".strip().lower(): 
                if self.has_textdisplay7:
                    obj.XinComponentTextDisplay7.draw(layout.box())
            if search == "" or search in "Text Display 8".strip().lower(): 
                if self.has_textdisplay8:
                    obj.XinComponentTextDisplay8.draw(layout.box())
            if search == "" or search in "Text Display 9".strip().lower(): 
                if self.has_textdisplay9:
                    obj.XinComponentTextDisplay9.draw(layout.box())
            if search == "" or search in "Text Display 10".strip().lower(): 
                if self.has_textdisplay10:
                    obj.XinComponentTextDisplay10.draw(layout.box())
            if search == "" or search in "Text Display 11".strip().lower(): 
                if self.has_textdisplay11:
                    obj.XinComponentTextDisplay11.draw(layout.box())
            if search == "" or search in "Text Display 12".strip().lower(): 
                if self.has_textdisplay12:
                    obj.XinComponentTextDisplay12.draw(layout.box())
            if search == "" or search in "Text Display 13".strip().lower(): 
                if self.has_textdisplay13:
                    obj.XinComponentTextDisplay13.draw(layout.box())
            ### NEXT COMPONENT DRAW CALL
        
        pass
    
    #Actor.generate
    def generate(self, obj):
        print("Generating", obj)
        tag = ""
        
        # Gen Attributes
        if True:
            tag = f"<actor guid='{obj.XinGUID.value}' type='{self.type}' "
            if self.componentguid != 1: tag += f"componentguid='{self.componentguid}' "
            if self.has_flavor: 
                if not self.flavor == "none":
                    tag += f"flavor='{self.flavor}' " 
            if self.has_camerafocus: tag += f"camerafocus='{BOOL(self.camerafocus)}' " 
            if self.has_playercontrol: tag += f"playercontrol='{BOOL(self.playercontrol)}' " 
            if self.has_abe: tag += f"abe='{BOOL(self.abe)}' " 
            if self.has_allegiance: tag += f"allegiance='{self.allegiance}' " 
            if self.has_assetcomponent: tag += f"assetcomponent='{self.assetcomponent}' " 
            if self.has_destcamera: tag += f"destcamera='{BOOL(self.destcamera)}' " 
            if self.has_destlayout: tag += f"destlayout='{BOOL(self.destlayout)}' " 
            if self.has_destteleporter: tag += f"destteleporter='{self.destteleporter}' " 
            if self.has_collidetype: tag += f"collidetype='{self.collidetype}' " 
            if self.has_pickup: tag += f"pickup='{self.pickup}' " 
            if self.has_envfilename: tag += f"envfilename='{self.envfilename}' " 
            if self.has_filename: tag += f"filename='{self.filename}' " 
            if self.has_healthycolor: tag += f"healthycolor='{COLOR(self.healthycolor)}' " 
            if self.has_unhealthycolor: tag += f"unhealthycolor='{COLOR(self.unhealthycolor)}' " 
            if self.has_spawntype: tag += f"spawntype='{self.spawntype}' " 
            if self.has_offdelay: tag += f"offdelay='{self.offdelay}' " 
            if self.has_acceptancelist: tag += f"acceptancelist='{self.acceptancelist.generate(obj)}' "
            if self.has_breed: tag += f"breed='{self.breed}' " 
            if self.has_delay: tag += f"delay='{self.delay}' " 
            if self.has_destguid: 
                if self.destguid == None:
                    INFO("Destination needs to be set or removed!")
                else:
                    tag += f"destguid='{self.destguid}' "
            if self.has_launchheight: tag += f"launchheight='{self.launchheight}' " 
            if self.has_rejectdest: tag += f"rejectdest='{VECT(self.rejectdest_object.matrix_world.to_translation())}' " 
            if self.has_rejectheight: tag += f"rejectheight='{self.rejectheight}' "
            if self.has_state: 
                if not self.state == "none":
                    tag += f"state='{self.state}' " 
            if self.has_style: 
                if not self.style == "none":
                    tag += f"style='{self.style}' " 
            if self.has_switchtocam: tag += f"switchtocam='{self.switchtocam}' " 
            if self.has_launchdest: tag += f"launchdest='{VECT(self.launchdest_object.matrix_world.to_translation())}' " 
            if self.has_actorfall: tag += f"actorfall='{BOOL(self.actorfall)}' " 
            if self.has_maxactive: tag += f"maxactive='{self.maxactive}' " 
            if self.has_maxspawn: tag += f"maxspawn='{self.maxspawn}' " 
            if self.has_spawndelay: tag += f"spawndelay='{self.spawndelay}' " 
            if self.has_spawnlist: tag += f"spawnlist='{self.spawnlist.generate(obj)}' " 
            if self.has_active: tag += f"active='{BOOL(self.active)}' " 
            if self.has_minlevel: tag += f"minlevel='{self.minlevel}' " 
            if self.has_ondelay: tag += f"ondelay='{self.ondelay}' " 
            if self.has_height: tag += f"height='{self.height}' " 
            if self.has_length: tag += f"length='{self.length}' " 
            if self.has_width: tag += f"width='{self.width}' " 
            if self.has_ambientcolor: tag += f"ambientcolor='{COLOR(self.ambientcolor)}' " 
            if self.has_diffusecolor: tag += f"diffusecolor='{COLOR(self.diffusecolor)}' " 
            if self.has_lightshape: tag += f"lightshape='{self.lightshape}' " 
            if self.has_lighttype: tag += f"lighttype='{self.lighttype}' " 
            if self.has_radius: tag += f"radius='{self.radius}' " 
            if self.has_isready: tag += f"isready='{BOOL(self.isready)}' " 
            if self.has_hotspotoffset: tag += f"hotspotoffset='{self.hotspotoffset}' " 
            if self.has_linkcomponent: tag += f"linkcomponent='{self.linkcomponent}' " 
            if self.has_levertype: tag += f"levertype='{self.levertype}' " 
            if self.has_health: tag += f"health='{self.health}' " 
            if self.has_moolah: tag += f"moolah='{self.moolah}' " 
            if self.has_moolahmax: tag += f"moolahmax='{self.moolahmax}' " 
            if self.has_spooceball: tag += f"spooceball='{self.spooceball}' " 
            if self.has_istouchactivated: tag += f"istouchactivated='{BOOL(self.istouchactivated)}' " 
            if self.has_visible: tag += f"visible='{BOOL(self.visible)}' " 
            if self.has_ontime: tag += f"ontime='{self.ontime}' " 
            if self.has_assetamount: tag += f"assetamount='{self.assetamount}' " 
            if self.has_linkcomponentguid: tag += f"linkcomponentguid='{self.linkcomponentguid}' " 
            if self.has_multidisplayguid: 
                if self.multidisplayguid != None: 
                    tag += f"multidisplayguid='{self.multidisplayguid.XinGUID.value}' " 
            if self.has_partialpayment: tag += f"partialpayment='{BOOL(self.partialpayment)}' " 
            if self.has_script: tag += f"script='{self.script}' " 
            if self.has_spooce: tag += f"spooce='{self.spooce}' " 
            if self.has_spoocemax: tag += f"spoocemax='{self.spoocemax}' " 
            if self.has_buttonradius: tag += f"buttonradius='{self.buttonradius}' " 
            if self.has_chantradius: tag += f"chantradius='{self.chantradius}' " 
            if self.has_particlevalue: tag += f"particlevalue='{self.particlevalue}' " 
            if self.has_shadowtype: tag += f"shadowtype='{self.shadowtype}' " 
            if self.has_percentlevel: tag += f"percentlevel='{self.percentlevel}' " 
            if self.has_multiteleport: tag += f"multiteleport='{BOOL(self.multiteleport)}' " 
            if self.has_activation: tag += f"activation='{self.activation}' " 
            if self.has_lensflaretype: tag += f"lensflaretype='{self.lensflaretype}' " 
            if self.has_lightdirection: tag += f"lightdirection='{VECT(self.lightdirection)}' " 
            if self.has_xaxis: tag += f"xaxis='{VECT(self.xaxis)}' " 
            if self.has_yaxis: tag += f"yaxis='{VECT(self.yaxis)}' " 
            if self.has_zaxis: tag += f"zaxis='{VECT(self.zaxis)}' " 
            if self.has_killifyouhaveto: tag += f"killifyouhaveto='{BOOL(self.killifyouhaveto)}' " 
            if self.has_maxaliveordead: tag += f"maxaliveordead='{self.maxaliveordead}' " 
            if self.has_deadlist: tag += f"deadlist='{self.deadlist.generate(obj)}' " 
            if self.has_prototypeguid: tag += f"prototypeguid='{self.prototypeguid}' " 
            if self.has_greetmsg: tag += f"greetmsg='{self.greetmsg}' " 
            if self.has_notreadymsg: tag += f"notreadymsg='{self.notreadymsg}' " 
            if self.has_direction: tag += f"direction='{VECT(self.direction)}' " 
            if self.has_minalpha: tag += f"minalpha='{self.minalpha}' " 
            if self.has_maxalpha: tag += f"maxalpha='{self.maxalpha}' " 
            if self.has_canclimb: tag += f"canclimb='{BOOL(self.canclimb)}' " 
            if self.has_scale: tag += f"scale='{self.scale}' " 
            if self.has_xvelocity: tag += f"xvelocity='{self.xvelocity}' " 
            if self.has_yvelocity: tag += f"yvelocity='{self.yvelocity}' " 
            if self.has_attenuation: tag += f"attenuation='{self.attenuation}' " 
            if self.has_amplitude: tag += f"amplitude='{self.amplitude}' " 
            if self.has_frequency: tag += f"frequency='{self.frequency}' " 
            if self.has_xoffset: tag += f"xoffset='{self.xoffset}' " 
            if self.has_yoffset: tag += f"yoffset='{self.yoffset}' " 
            if self.has_healthmax: tag += f"healthmax='{self.healthmax}' " 
            if self.has_shadowopacity: tag += f"shadowopacity='{self.shadowopacity}' " 
            if self.has_specularcolor: tag += f"specularcolor='{COLOR(self.specularcolor)}' " 
            if self.has_force: tag += f"force='{self.force}' " 
            if self.has_particles: tag += f"genericparticles='{self.particles}' " 
            if self.has_size: tag += f"size='{VECT(self.size)}' " 
            if self.has_body: tag += f"body='{self.body}' " 
            if self.has_errdisplayguid: tag += f"errdisplayguid='{self.errdisplayguid}' " 
            if self.has_lowassetmsg: tag += f"lowassetmsg='{self.lowassetmsg}' " 
            if self.has_particleoffset: tag += f"particleoffset='{VECT(self.particleoffset)}' " 
            if self.has_errordelay: tag += f"errordelay='{self.errordelay}' " 
            if self.has_exclusive: tag += f"exclusive='{self.exclusive}' " 
            if self.has_componentlink: tag += f"componentlink='{self.componentlink}' " 
            if self.has_rescuetheseflavors: tag += f"rescuetheseflavors='{self.rescuetheseflavors}' " 
            if self.has_fadedistance: tag += f"fadedistance='{self.fadedistance}' " 
            if self.has_divisor: tag += f"divisor='{self.divisor}' " 
            if self.has_amplitude1: tag += f"amplitude1='{self.amplitude1}' " 
            if self.has_amplitude2: tag += f"amplitude2='{self.amplitude2}' " 
            if self.has_countingorder: tag += f"countingorder='{self.countingorder}' " 
            if self.has_droppoint: tag += f"droppoint='{VECT(self.droppoint)}' " 
            if self.has_turnoffdelay: tag += f"turnoffdelay='{self.turnoffdelay}' " 
            if self.has_bpheight: tag += f"bpheight='{self.bpheight}' " 
            if self.has_inverted: tag += f"inverted='{self.inverted}' "
            tag += ">"
            
            #a = input(tag)
            
        
        self.generate_component_guids(obj)
        # Gen Components
        if True:
            if self.has_legmotion:
                tag += obj.XinComponentLegMotion.generate(obj)
            if self.has_flyingmotion:
                tag += obj.XinComponentFlyingMotion.generate(obj)
            if self.has_simplemotion:
                tag += obj.XinComponentSimpleMotion.generate(obj)
            if self.has_ear:
                tag += obj.XinComponentEar.generate(obj)
            if self.has_munchanimation:
                tag += obj.XinComponentMunchAnimation.generate(obj)
            if self.has_mudokonanimation:
                tag += obj.XinComponentMudokonAnimation.generate(obj)
            if self.has_simpleanimation:
                tag += obj.XinComponentSimpleAnimation.generate(obj)
            if self.has_dooranimation:
                tag += obj.XinComponentDoorAnimation.generate(obj)
            if self.has_teleporteranimation:
                tag += obj.XinComponentTeleporterAnimation.generate(obj)
            if self.has_sliganimation:
                tag += obj.XinComponentSligAnimation.generate(obj)
            if self.has_lever360animation:
                tag += obj.XinComponentLever360Animation.generate(obj)
            if self.has_footswitchanimation:
                tag += obj.XinComponentFootSwitchAnimation.generate(obj)
            if self.has_fuzzleanimation:
                tag += obj.XinComponentFuzzleAnimation.generate(obj)
            if self.has_vendingmachineanimation:
                tag += obj.XinComponentVendingMachineAnimation.generate(obj)
            if self.has_bigbroanimation:
                tag += obj.XinComponentBigBroAnimation.generate(obj)
            if self.has_nullanimation:
                obj.XinComponentNullAnimation.generate(obj)
            if self.has_glukkonanimation:
                obj.XinComponentGlukkonAnimation.generate(obj)
            if self.has_wheelchairanimation:
                obj.XinComponentWheelchairAnimation.generate(obj)
            if self.has_paramiteanimation:
                obj.XinComponentParamiteAnimation.generate(obj)
            if self.has_scrabanimation:
                obj.XinComponentScrabAnimation.generate(obj)
            if self.has_genericparticlesanimation:
                obj.XinComponentGenericParticlesAnimation.generate(obj)
            if self.has_meepanimation:
                tag += obj.XinComponentMeepAnimation.generate(obj)
            if self.has_internanimation:
                tag += obj.XinComponentInternAnimation.generate(obj)
            if self.has_sloganimation:
                tag += obj.XinComponentSlogAnimation.generate(obj)
            if self.has_vykkeranimation:
                tag += obj.XinComponentVykkerAnimation.generate(obj)
            if self.has_recycleranimation:
                tag += obj.XinComponentRecyclerAnimation.generate(obj)
            if self.has_candystriperanimation:
                tag += obj.XinComponentCandyStriperAnimation.generate(obj)
            if self.has_behavior:
                tag += obj.XinComponentBehavior.generate(obj)
            if self.has_job:
                tag += obj.XinComponentJob.generate(obj)
            if self.has_doves:
                tag += obj.XinComponentDoves.generate(obj)
            if self.has_zapfx:
                tag += obj.XinComponentZapFx.generate(obj)
            if self.has_assetlock:
                tag += obj.XinComponentAssetLock.generate(obj)
            if self.has_sparklestream:
                tag += obj.XinComponentSparkleStream.generate(obj)
            if self.has_weapon:
                tag += obj.XinComponentWeapon.generate(obj)
            if self.has_broadcaster:
                tag += obj.XinComponentBroadcaster.generate(obj)
            if self.has_collectable:
                tag += obj.XinComponentCollectable.generate(obj)
            if self.has_powerup:
                tag += obj.XinComponentPowerUp.generate(obj)
            if self.has_shadow:
                tag += obj.XinComponentShadow.generate(obj)
            if self.has_lifecycle:
                tag += obj.XinComponentLifeCycle.generate(obj)
            if self.has_explosion:
                tag += obj.XinComponentExplosion.generate(obj)
            if self.has_target:
                tag += obj.XinComponentTarget.generate(obj)
            if self.has_bullseye:
                tag += obj.XinComponentBullseye.generate(obj)
            if self.has_shortgoal:
                tag += obj.XinComponentShortGoal.generate(obj)
            if self.has_transformer:
                tag += obj.XinComponentTransformer.generate(obj)
            if self.has_onoffswitch:
                tag += obj.XinComponentOnOffSwitch.generate(obj)
            if self.has_attachmentspawner:
                tag += obj.XinComponentAttachmentSpawner.generate(obj)
            if self.has_floatation:
                tag += obj.XinComponentFloatation.generate(obj)
            if self.has_actortally:
                tag += obj.XinComponentActorTally.generate(obj)
            if self.has_actortally2:
                tag += obj.XinComponentActorTally2.generate(obj)
            if self.has_actortally3:
                tag += obj.XinComponentActorTally3.generate(obj)
            if self.has_actortally4:
                tag += obj.XinComponentActorTally4.generate(obj)
            if self.has_actortally5:
                tag += obj.XinComponentActorTally5.generate(obj)
            if self.has_textdisplay:
                tag += obj.XinComponentTextDisplay.generate(obj)
            if self.has_textdisplay2:
                tag += obj.XinComponentTextDisplay2.generate(obj)
            if self.has_textdisplay3:
                tag += obj.XinComponentTextDisplay3.generate(obj)
            if self.has_textdisplay4:
                tag += obj.XinComponentTextDisplay4.generate(obj)
            if self.has_textdisplay5:
                tag += obj.XinComponentTextDisplay5.generate(obj)
            if self.has_textdisplay6:
                tag += obj.XinComponentTextDisplay6.generate(obj)
            if self.has_textdisplay7:
                tag += obj.XinComponentTextDisplay7.generate(obj)
            if self.has_textdisplay8:
                tag += obj.XinComponentTextDisplay8.generate(obj)
            if self.has_textdisplay9:
                tag += obj.XinComponentTextDisplay9.generate(obj)
            if self.has_textdisplay10:
                tag += obj.XinComponentTextDisplay10.generate(obj)
            if self.has_textdisplay11:
                tag += obj.XinComponentTextDisplay11.generate(obj)
            if self.has_textdisplay12:
                tag += obj.XinComponentTextDisplay12.generate(obj)
            if self.has_textdisplay13:
                tag += obj.XinComponentTextDisplay13.generate(obj)
            ### NEXT HAS COMPONENT GENERATE
            tag += "</actor>"
        return tag
    
    
    #Use this to show the tag select menu
    # bpy.ops.wm.call_menu(name="XinTag_AddComponent_or_Property")
    # only show a property to add if that properties flag is set to false else skip it as it is already there
    # presets will automatically set up actors to have components and properties when selected in the add menu
    # menu has preset components and individual properties
    # each item does 
    # obj = Context.Object
    # example for add behaviour component
    # obj.Actor.hasBehaviour = true
    # obj.Actor.hasEnabled = true
    # obj.Actor.hasVariables = true
    # obj.Actor.hasScript = true
    
    # A list would be added like this
    # obj.Actor.hasActorList = true
    # the actor count will be shown as well as the button to hide the list for viewing clarity
    
    
    # the draw and generate methods will do stuff based on what is enebled
    pass

class Waypoint(PropertyGroup):
    
    def update_num_navpaths(self, context):
        obj = context.object
        while len(obj.XinComponentNavPaths) > self.num_navpaths:
            obj.XinComponentNavPaths.remove(len(obj.XinComponentNavPaths)-1)
        while len(obj.XinComponentNavPaths) < self.num_navpaths:
            obj.XinComponentNavPaths.add()
    
    def update_mesh(self, context):
        update_mesh(context)
    
    has_entrypoint: BoolProperty(name="Has Entry Point", description="",default=False)
    entrypoint: BoolProperty(
        name="Entry Point", description="",
        default=True
    )
    
    show_navpaths: BoolProperty(
        name="Show Hide Navpaths",
        description="Show or hide the navpaths",
        default=False
    )
    
    num_navpaths: IntProperty(
        name="NavPath Count",
        description="The number of navpaths in this waypoint",
        default=0,
        min=0,
        update=update_num_navpaths
    )
    
    showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
    
    class NavPath(PropertyGroup):
        showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
        
        has_action: BoolProperty(name="Has Action", description="",default=True)
        action: EnumProperty(
            name="Action", description="",
            items=[
                ("kWalk","kWalk","Generated from Real Data"),
                ("kLadder","kLadder","Generated from Real Data")
            ]
        )

        has_nextwaypoint: BoolProperty(name="Has Next Waypoint", description="",default=True)
        nextwaypoint: PointerProperty(
            name="Next Waypoint", description="The next waypoint in the sequence",
            type=bpy.types.Object,
            poll=poll_waypoints
        )

        def draw(self, layout):
            layout.label(text="Nav Path Component")
            layout.prop(self, "showHasAttr",toggle=1)
            if self.showHasAttr:
                box = layout.box()
                box.prop(self, "has_action")
                box.prop(self, "has_guid")
            if self.has_action: layout.prop(self, "action")
            if self.has_nextwaypoint: layout.prop(self, "nextwaypoint")

        def generate(self, obj):
            tag = f"<navpath "
            if self.has_action: tag += f"action='{self.action}' "
            if self.has_nextwaypoint: tag += f"guid='{self.nextwaypoint.guid}' "
            tag += "/>"
            return tag


    def draw(self, layout, obj):
        layout.label(text="Waypoint")
        layout.prop(self, "showHasAttr",toggle=1)
        if self.showHasAttr:
            box = layout.box()
            box.prop(self, "has_entrypoint")
        if self.has_entrypoint: layout.prop(self, "entrypoint")
        layout.prop(self, "show_navpaths", toggle=True)
        if self.show_navpaths:
            layout.prop(self, "num_navpaths")
            for i in range(self.num_navpaths):
                obj.XinComponentNavPaths[i].draw(layout.box())

    def generate(self, obj):
        tag = f"<waypoint guid='{obj.XinGUID.value}' "
        if self.has_entrypoint: tag += f"entrypoint='{self.entrypoint}' "
        tag += genTransform(obj)
        if self.num_navpaths == 0: tag += "/>"
        else:
            tag += ">"
            for i in range(self.num_navpaths):
                tag += obj.XinComponentNavPaths[i].generate(obj)
            tag += "</waypoint>"
        return tag

class Camera(PropertyGroup):
    has_abecam: BoolProperty(name="Has Abe Cam", description="",default=False)
    has_bgcolor: BoolProperty(name="Has Bg Color", description="",default=False)
    has_camheight: BoolProperty(name="Has Cam Height", description="",default=False)
    has_camtype: BoolProperty(name="Has Cam Type", description="",default=True)
    has_defcam: BoolProperty(name="Has Def Cam", description="",default=True)
    has_fogcolor: BoolProperty(name="Has Fog Color", description="",default=False)
    has_fogdepth: BoolProperty(name="Has Fog Depth", description="",default=False)
    has_fogsetting: BoolProperty(name="Has Fog Setting", description="",default=True)
    has_followmax: BoolProperty(name="Has Follow Max", description="",default=True)
    has_followmin: BoolProperty(name="Has Follow Min", description="",default=True)
    has_heading: BoolProperty(name="Has Heading", description="",default=False)
    has_lookdist: BoolProperty(name="Has Look Dist", description="",default=False)
    has_lookheight: BoolProperty(name="Has Look Height", description="",default=False)
    has_munchcam: BoolProperty(name="Has Munch Cam", description="",default=False)
    has_lensfactor: BoolProperty(name="Has Lens Factor", description="",default=False)
    has_centery: BoolProperty(name="Has Center Y", description="",default=False)
    has_heightmax: BoolProperty(name="Has Height Max", description="",default=False)
    has_lockheading: BoolProperty(name="Has Lock Heading", description="",default=False)
    has_pitch: BoolProperty(name="Has Pitch", description="",default=False)
    has_followclosethresh: BoolProperty(name="Has Follow Close Thresh", description="",default=False)
    has_lookspeed: BoolProperty(name="Has Look Speed", description="",default=False)
    has_centerx: BoolProperty(name="Has Center X", description="",default=False)
    has_followcloseslide: BoolProperty(name="Has Follow Close Slide", description="",default=False)
    has_followcloseheight: BoolProperty(name="Has Follow Close Height", description="",default=False)
    has_jumplookfactor: BoolProperty(name="Has Jump Look Factor", description="",default=False)
    has_enabledpad: BoolProperty(name="Has Enable Dpad", description="",default=False)
    has_farclip: BoolProperty(name="Has Far Clip", description="",default=False)
    has_orcam: BoolProperty(name="Has Orbit Cam", description="",default=False)
    has_jumplookdelay: BoolProperty(name="Has Jump Look Delay", description="",default=False)
    has_movespeed: BoolProperty(name="Has Move Speed", description="",default=False)
    has_obcamtimeout: BoolProperty(name="Has Obstruction Cam Time Out", description="",default=False)
    has_obcamtranstime: BoolProperty(name="Has Obstruction Cam Trans Time", description="",default=False)
    has_obstructioncamid: BoolProperty(name="Has Obstruction Cam Id", description="",default=False)
    has_obstructswitch: BoolProperty(name="Has Obstruct Switch", description="",default=False)
    has_anchorpos: BoolProperty(name="Has Anchor Pos", description="",default=False)
    has_rotspeed: BoolProperty(name="Has Rot Speed", description="",default=False)
    has_zmovefactor: BoolProperty(name="Has Z Move Factor", description="",default=False)
    has_nocollidetest: BoolProperty(name="Has No Collide Test", description="",default=False)
    has_noobstructtest: BoolProperty(name="Has No Obstruct Test", description="",default=False)
    has_novertobthresh: BoolProperty(name="Has No Vert Obstruct Thresh", description="",default=False)
    has_relativeanchorz: BoolProperty(name="Has Relative Anchor Z", description="",default=False)
    has_heightmin: BoolProperty(name="Has Height Min", description="",default=False)
    
    abecam: BoolProperty(name="Abe Cam", description="",default=False)
    bgcolor: FloatVectorProperty(name="Background Color", description="",subtype="COLOR",min=0, max=1,default=(0.2705882,0.5372549,0.7176471))
    camheight: FloatProperty(name="Cam Height", description="",default=10.0)
    camtype: EnumProperty(name="Cam Type", description="",items=[("follow","follow","Generated default with script")],default="follow")
    defcam: BoolProperty(name="Def Cam", description="",default=False)
    fogcolor: FloatVectorProperty(name="Fog Color", description="",subtype="COLOR",min=0, max=1,default=(0.2705882,0.5372549,0.7176471))
    fogdepth: FloatProperty(name="Fog Depth", description="",default=0.75)
    fogsetting: EnumProperty(name="Fog Setting", description="",items=[("default","default","Generated default with script")],default="default")
    followmax: FloatProperty(name="Follow Max", description="",default=80.0)
    followmin: FloatProperty(name="Follow Min", description="",default=50.0)
    heading: FloatProperty(name="Heading", description="",default=0.0,min=-180.0,max=180.0)
    lookdist: FloatProperty(name="Look Dist", description="",default=0.0)
    lookheight: FloatProperty(name="Look Height", description="",default=15.0)
    munchcam: BoolProperty(name="Munch Cam", description="",default=False)
    lensfactor: FloatProperty(name="Lens Factor", description="",default=1.0)
    centery: FloatProperty(name="Center Y", description="",default=0.5)
    centerx: FloatProperty(name="Center X", description="",default=0.5)
    heightmax: FloatProperty(name="Height Max", description="",default=75.0)
    lockheading: BoolProperty(name="Lock Heading", description="",default=False)
    pitch: FloatProperty(name="Pitch", description="",default=0.0,min=180.0,max=180.0)
    followclosethresh: FloatProperty(name="Follow Close Thresh", description="",default=0.0)
    lookspeed: FloatProperty(name="Look Speed", description="",default=0.25)
    followcloseslide: FloatProperty(name="Follow Close Slide", description="",default=0.0)
    followcloseheight: FloatProperty(name="Follow Close Height", description="",default=0.0)
    jumplookfactor: FloatProperty(name="Jump Look Factor", description="",default=0.1)
    enabledpad: BoolProperty(name="Enable Dpad", description="",default=True)
    farclip: FloatProperty(name="Far Clip", description="",default=800.0)
    orcam: BoolProperty(name="Orbit Cam", description="",default=False)
    jumplookdelay: FloatProperty(name="Jump Look Delay", description="",default=0.5)
    movespeed: FloatProperty(name="Move Speed", description="",default=0.25)
    obcamtimeout: FloatProperty(name="Obstruction Cam Time Out", description="",default=0)
    obcamtranstime: FloatProperty(name="Obstruction Cam Trans Time", description="",default=0)
    obstructioncamid: PointerProperty(name="Obstruction Cam Id", description="",type=bpy.types.Object, poll=poll_cameras)
    obstructswitch: BoolProperty(name="Obstruct Switch", description="",default=False)
    anchorpos: FloatVectorProperty(name="Anchor Pos", description="",subtype="XYZ",default=(0,0,0))
    rotspeed: FloatProperty(name="Rot Speed", description="",default=0.0)
    zmovefactor: FloatProperty(name="Z Move Factor", description="",default=0.5)
    nocollidetest: BoolProperty(name="No Collide Test", description="",default=False)
    noobstructtest: BoolProperty(name="No Obstruct Test", description="",default=False)
    novertobthresh: BoolProperty(name="No Vert Obstruct Thresh", description="",default=False)
    relativeanchorz: BoolProperty(name="Relative Anchor Z", description="",default=False)
    heightmin: FloatProperty(name="Height Min", description="",default=0.0)
    
    search: StringProperty(name="Search", description="filters the properties",default="")
    showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
    
    def draw(self, layout, obj):
        layout.label(text="Camera")
        layout.prop(self, "showHasAttr",toggle=1)
        LAYOUT_PROP_LST(layout, self, [
            "abecam","bgcolor","camheight","camtype","defcam","fogcolor","fogdepth","fogsetting","followmax",
            "followmin","heading","lookdist","lookheight","munchcam","lensfactor","centery","heightmax","lockheading",
            "pitch","followclosethresh","lookspeed","centerx","followcloseslide","followcloseheight","jumplookfactor",
            "enabledpad","farclip","orcam","jumplookdelay","movespeed","obcamtimeout","obcamtranstime","obstructioncamid",
            "obstructswitch","anchorpos","rotspeed","zmovefactor","nocollidetest","noobstructtest","novertobthresh",
            "relativeanchorz","heightmin"
        ], self.showHasAttr)
            
    def generate(self, obj):
        tag = f"<camera guid='{obj.XinGUID.value}' "
        tag = GENERATE_PROP_LST(tag, self, [
            "abecam","bgcolor","camheight","camtype","defcam",
            "fogcolor","fogdepth","fogsetting","followmax","followmin",
            "heading","lookdist","lookheight","munchcam","lensfactor",
            "centery","heightmax","lockheading","pitch","followclosethresh",
            "lookspeed","centerx","followcloseslide","followcloseheight",
            "jumplookfactor","enabledpad","farclip","orcam","jumplookdelay",
            "movespeed","obcamtimeout","obcamtranstime","obstructioncamid",
            "obstructswitch","anchorpos","rotspeed","zmovefactor","nocollidetest",
            "noobstructtest","novertobthresh","relativeanchorz","heightmin"
        ])
        tag += genTransform(obj)
        tag += "/>"
        return tag

class CameraTransition(PropertyGroup):
    
    def update_width(self, context):
        update_mesh(context)
    
    def update_height(self, context):
        update_mesh(context)
    
    has_flavor: BoolProperty(name="Has Flavor", description="",default=False)
    flavor: EnumProperty(name="Flavor", description="DESCVAL", items=[
            ("player", "Player", "")
        ],
        default="player")
    
    has_destcam: BoolProperty(name="Has Dest Cam", description="",default=False)
    destcam: IntProperty(name="Dest Cam", description="",default=0)
    
    has_height: BoolProperty(name="Has Height", description="",default=False)
    height: FloatProperty(name="Height", description="",default=10.0, update=update_height)
    
    has_width: BoolProperty(name="Has Width", description="",default=False)
    width: FloatProperty(name="Width", description="",default=10.0, update=update_width)
    
    has_time: BoolProperty(name="Has Time", description="",default=False)
    time: FloatProperty(name="Time", description="",default=0.5)
    
    has_holdtime: BoolProperty(name="Has Hold Time", description="",default=False)
    holdtime: FloatProperty(name="Hold Time", description="",default=0.0)
    
    has_cttype: BoolProperty(name="Has Ct Type", description="",default=False)
    cttype: EnumProperty(name="Ct Type", description="",items=[
            ("move","move","Generated default with script")
        ],
        default="move")
    
    has_isactive: BoolProperty(name="Has Is Active", description="",default=True)
    isactive: BoolProperty(name="Is Active", description="",default=True)
    
    has_srccam: BoolProperty(name="Has Src Cam", description="",default=False)
    srccam: IntProperty(name="Src Cam", description="",default=0)
    
    has_orientation: BoolProperty(name="Has Orientation",description="DESCVAL",default=True)
    orientation: EnumProperty(name="Orientation",description="DESCVAL",items=[
            ("vertical", "Vertical", "DESCVAL"),
            ("horiz. up", "Horizontal Up", "DESCVAL"),
            ("horiz. down", "Horizontal Down", "DESCVAL")
        ])
    
    
    search: StringProperty(name="Search", description="filters the properties",default="" )
    showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
    
    def draw(self, layout, obj):
        layout.label(text="Camera Transition")
        layout.prop(self, "showHasAttr",toggle=1)
        
        LAYOUT_PROP_LST(layout, self, [
            "flavor",
            "destcam","height","width","time",
            "cttype","isactive","srccam", "orientation"
        ], self.showHasAttr)
        
    def generate(self, obj):
        tag = f"<cameratransition "
        tag += f"guid='{obj.XinGUID.value}' "
        tag = GENERATE_PROP_LST(tag, self, [
            "flavor", "destcam", "width", "height",
            "time", "holdtime", "cttype", "isactive",
            "srccam", "orientation"
        ])
        
        tag += genTransform(obj)
        tag += "/>"
        return tag

class ScriptTrigger(PropertyGroup):

    def update_width(self, context):
        update_mesh(context)
        
    def update_height(self, context):
        update_mesh(context)
    
    has_isactive: BoolProperty(name="Has Is Active",description="DESCVAL",default=True)
    isactive: BoolProperty(name="Is Active",description="DESCVAL",default=True)
    
    has_width: BoolProperty(name="Has Width",description="DESCVAL",default=True)
    width:  FloatProperty(name="Width",description="DESCVAL",default=10.0,update=update_width)
    
    has_height: BoolProperty(name="Has Height",description="DESCVAL",default=True)
    height:  FloatProperty(name="Height",description="DESCVAL",default=10.0,update=update_height)
    
    has_orientation: BoolProperty(name="Has Orientation",description="DESCVAL",default=True)
    orientation: EnumProperty(name="Orientation",description="DESCVAL",items=[
            ("vertical", "Vertical", "DESCVAL"),
            ("horiz. up", "Horizontal Up", "DESCVAL"),
            ("horiz. down", "Horizontal Down", "DESCVAL")
        ],
        default="vertical")
    
    has_script: BoolProperty(name="Has Script",description="DESCVAL",default=True)
    script: StringProperty(name="Script",description="DESCVAL",default="none")
    
    search: StringProperty(name="Filter",description="DESCVAL",default="")
    show_has: BoolProperty(name="Add/Remove Attributes",description="DESCVAL",default=False)
    
    def draw(self, layout, obj):
        layout.label(text="Script Trigger")
        layout.prop(self, "show_has", toggle=1)
        LAYOUT_PROP_LST( layout, self, [
            "isactive","width","height",
            "orientation","script"
        ], self.show_has)
        pass
    
    def generate(self, obj):
        tag = f"<scripttrigger guid='{obj.XinGUID.value}' "
        tag = GENERATE_PROP_LST(tag, self, [
            "isactive", "width", "height",
            "orientation", "script"
        ])
        tag += "/>"
        return tag

class LayoutTransition(PropertyGroup):
    
    
    def update_width(self, context):
        update_mesh(context)
    
    def update_height(self, context):
        update_mesh(context)
    
    has_flavor: BoolProperty(name="Has Flavor", description="DESCVAL",default=False)
    flavor: EnumProperty(name="Flavor", description="DESCVAL", items=[
                ("layout","layout","Generated default with script"),
                ("enviroment","enviroment","Generated default with script")
        ],
        default="layout")

    has_isactive: BoolProperty(name="Has Is Active", description="DESCVAL",default=False)
    isactive: BoolProperty(name="Is Active", description="DESCVAL", default=True)

    has_width: BoolProperty(name="Has Width", description="DESCVAL",default=False)
    width: FloatProperty(name="Width", description="DESCVAL", default=10.0, update=update_width)

    has_height: BoolProperty(name="Has Height", description="DESCVAL",default=False)
    height: FloatProperty(name="Height", description="DESCVAL", default=10.0, update=update_height)

    has_layout: BoolProperty(name="Has Layout", description="DESCVAL",default=False)
    layout: StringProperty(name="Layout", description="DESCVAL", default="")

    has_destcam: BoolProperty(name="Has Dest Cam", description="DESCVAL",default=False)
    destcam: IntProperty(name="Dest Cam", description="DESCVAL", default=0)

    has_destpos: BoolProperty(name="Has Dest Pos", description="DESCVAL",default=False)
    destpos: FloatVectorProperty(name="Dest Pos", description="DESCVAL", subtype="XYZ",default=(0.0,0.0,0.0))

    has_destplayer: BoolProperty(name="Has Dest Player", description="DESCVAL",default=False)
    destplayer: IntProperty(name="Dest Player", description="DESCVAL", default=0)

    has_lttype: BoolProperty(name="Has Lt Type", description="DESCVAL",default=False)
    lttype: EnumProperty(name="Lt Type", description="DESCVAL", items=[
                ("cut","cut","Generated default with script"),
                ("fade","fade","Generated default with script"),
                ("script","script","Generated default with script")
        ],
        default="cut")

    has_orientation: BoolProperty(name="Has Orientation", description="DESCVAL",default=False)
    orientation: EnumProperty(name="Orientation", description="DESCVAL", items=[
                ("vertical","vertical","Generated default with script"),
                ("horis. up","horis. up","Generated default with script"),
                ("horiz. down","horiz. down","Generated default with script")
        ],
        default="vertical")

    showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
    search: StringProperty(name="Filter", description="Filters the list of attributes", default="")

    def draw(self, layout, obj):
        layout.label(text="Layout Transition")
        layout.prop(self, "showHasAttr", toggle=1)
        LAYOUT_PROP_LST(layout, self, [
                "flavor","isactive","width","height",
                "layout","destcam","destpos","destplayer",
                "lttype","orientation"
            ], self.showHasAttr)

    def generate(self, obj):
        tag = f"<layouttransition guid='{obj.XinGUID.value}' "
        tag = GENERATE_PROP_LST(tag, self, [
                "flavor","isactive","width","height",
                "layout","destcam","destpos","destplayer",
                "lttype","orientation"
            ])
        tag += genTransform(obj)
        tag += "/>"
        return tag

class Ambiance(PropertyGroup):
    has_radius: BoolProperty(name="Has Radius", description="DESCVAL",default=False)
    radius: FloatProperty(name="Radius", description="DESCVAL", default=100.0)

    has_height: BoolProperty(name="Has Height", description="DESCVAL",default=False)
    height: FloatProperty(name="Height", description="DESCVAL", default=100.0)

    has_type: BoolProperty(name="Has Type", description="DESCVAL",default=False)
    type: EnumProperty(name="Type", description="DESCVAL", items=[
                ("silence","silence","Generated default with script"),
                ("birds","birds","Generated default with script"),
                ("water","water","Generated default with script"),
                ("fire","fire","Generated default with script")
        ],
        default="silence")

    has_emitoffset: BoolProperty(name="Has Offset", description="DESCVAL",default=False)
    emitoffset: FloatVectorProperty(name="Offset", description="DESCVAL", subtype="XYZ",default=(0.0,0.0,0.0))

    has_emitradius: BoolProperty(name="Has Radius", description="DESCVAL",default=False)
    emitradius: FloatProperty(name="Radius", description="DESCVAL", default=0.0)

    has_emitheight: BoolProperty(name="Has Height", description="DESCVAL",default=False)
    emitheight: FloatProperty(name="Height", description="DESCVAL", default=0.0)

    has_freqmin: BoolProperty(name="Has Min", description="DESCVAL",default=False)
    freqmin: FloatProperty(name="Min", description="DESCVAL", default=5.0)

    has_freqmax: BoolProperty(name="Has Max", description="DESCVAL",default=False)
    freqmax: FloatProperty(name="Max", description="DESCVAL", default=10.0)

    showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
    search: StringProperty(name="Filter", description="Filters the list of attributes", default="")

    def draw(self, layout, obj):
        layout.label(text="Ambiance")
        layout.prop(self, "showHasAttr", toggle=1)
        LAYOUT_PROP_LST(layout, self, [
                "radius","height","type","emitoffset",
                "emitradius","emitheight","freqmin","freqmax"
            ], self.showHasAttr)

    def generate(self, obj):
        tag = f"<ambiance guid='{obj.XinGUID.value}' "
        tag = GENERATE_PROP_LST(tag, self, [
                "radius","height","type","emitoffset",
                "emitradius","emitheight","freqmin","freqmax"
            ])
        tag += f"position='{genPos(obj.location)}'"
        tag += "/>"
        return tag

# These Navpaths exsist in game but are not used. they seem to be related to ladders. 
# Their GUIDs are never referenced in the scripts and also conflict with a waypoints GUID. this doesnt crash the game however it is just ignored
# I guess onece 1 GUID is assinged any other attempt to assign that GUID is ignored

class NavPath(PropertyGroup):
    has_action: BoolProperty(name="Has Action", description="DESCVAL",default=False)
    action: EnumProperty(name="Action", description="DESCVAL", items=[
                ("kWalk","kWalk","Generated default with script"),
                ("kLadder","kLadder","Generated default with script")
        ],
        default="kWalk")

    showHasAttr: BoolProperty(name="Add/Remove Attributes", description="Show the list of available attributes", default=False)
    search: StringProperty(name="Filter", description="Filters the list of attributes", default="")

    def draw(self, layout, obj):
        layout.label(text="Nav Path")
        layout.prop(self, "showHasAttr", toggle=1)
        LAYOUT_PROP_LST(layout, self, [
                "action"
            ], self.showHasAttr)

    def generate(self, obj):
        tag = f"<navpath guid='{obj.XinGUID.value}' "
        tag = GENERATE_PROP_LST(tag, self, [
                "action"
            ])
        tag += genTransform(obj)
        tag += "/>"
        return tag

""" Editor Only """
class GroundCreateOperator(Operator):
    bl_idname = "wm.groundcreate"
    bl_label = "Create"
    bl_description = "Click this to setup this Ground and start editing the position and size or the tilemap."
    
    def Create(self, context):
        obj = context.object
        obj.location[0] = 0.0
        obj.location[1] = 0.0
        obj.location[2] = 0.0
        set_modifier_node_group(obj, None)
        set_modifier_node_group(obj, "GROUND", "Ground_Grid")
        
        # load assets if nessecary
        
        
        pass
    
    def draw(self, context):
        pass
    
    def execute(self, context):
        self.Create(context)
        return {"FINISHED"}
class GroundApplyOperator(Operator):
    bl_idname = "wm.groundapply"
    bl_label = "Apply"
    bl_description = "Click this when you have finished sizing and positioning the ground.\nIt will place the generated grid ready for grass.\nThen create planes in the GRASS collectiona an position them above where you want grass to be."
    
    def Apply(self, context):
        
        
        
        pass
    
    def draw(self, context):
        pass
    
    def execute(self, context):
        self.Apply(context)
        return {"FINISHED"}
    
class Ground(PropertyGroup):
    
    def update_width(self, context):
        obj = context.object
        set_modifier_socket(obj, "GROUND", "Width", self.width, False)
        pass
    def update_height(self, context):
        obj = context.object
        set_modifier_socket(obj, "GROUND", "Height", self.height, False)
        pass
    def update_x(self, context):
        obj = context.object
        set_modifier_socket(obj, "GROUND", "X", self.x, False)
        pass
    def update_y(self, context):
        obj = context.object
        set_modifier_socket(obj, "GROUND", "Y", self.y, False)
        pass
    def update_z(self, context):
        obj = context.object
        set_modifier_socket(obj, "GROUND", "Z", self.z, False)
        pass
    
    
    
    width: FloatProperty(name="Width", description="Set the width of the tilemap (Limited from 1 to 100)", default=1, min=1, max=100, update=update_width)
    height: FloatProperty(name="Height", description="Set the height of the tilemap (Limited from 1 to 100)", default=1, min=1, max=100, update=update_height)
    x: FloatProperty(name="X", description="Set the X position of the tilemap on a grid (60m)", default=0, update=update_x)
    y: FloatProperty(name="Y", description="Set the Y position of the tilemap on a grid (60m)", default=0, update=update_y)
    z: FloatProperty(name="Z", description="Set the Z position of the tilemap on a grid (120m)", default=0, update=update_z)
    
    
    def draw(self, layout, obj):
        if not obj.modifiers.get("GROUND") == None and obj.modifiers.get("GROUND").node_group == bpy.data.node_groups["Ground_Grid"]:
            layout.operator(GroundApplyOperator.bl_idname, text=GroundApplyOperator.bl_label)
            layout.prop(self, "width")
            layout.prop(self, "height")
            layout.prop(self, "x")
            layout.prop(self, "y")
            layout.prop(self, "z")
        else:
            layout.operator(GroundCreateOperator.bl_idname, text=GroundCreateOperator.bl_label)
        
        pass

""" Operators """
#class RequestRandomOperator(Operator):
#    """Random Tag Requester"""
#    bl_idname = "wm.requestrandomtag"
#    bl_label = "Request Random Tag"
#    bl_description = "Retrieves a new tag to work on randomly to remove the burdon of choice"
#        
#    def RequestRandom(self):
#        global currenttag
#        devPG = bpy.context.scene.XinDev
#        #devOBJ = bpy.types.Object(bpy.data.objects.get("DevOBJ"))
#        if devPG.hascompletedtag:
#            devPG.hascompletedtag = False
#            path = "C:\\Users\\CZore\\source\\repos\\CZORE_Project_Platform\\MO_RegionIO_TestEnv\\bin\Debug\\tagdata\\RemainingTags.txt"
#            f = open(path, 'r')
#            lines = f.readlines()
#            f.close()
#
#            index = random.randint(0, len(lines))
#            devOBJ["currenttag"] = lines[index]
#            lines.pop(index)
#
#            f = open(path, 'w')
#            f.writelines(lines)
#            f.close()
#
#
#
#    def draw(self, layout):
#        layout = self.layout
#        
#        
#
#    def execute(self, context):
#        LOG("Request Random Tag")
#        self.RequestRandom()
#        return {'FINISHED'}

class LoadAllAssets_BTN(Operator):
    bl_idname = "motm.loadallassets"
    bl_label = "Load All Assets"
    bl_description = "Extracts assets from the games NIF files as obj(wavefront) models, So they can be loaded in blender. \n" + \
        "Also pulls models from the layouts for things that dont have an external model. \n\n" + \
        "WARNING: This function will freeze blender while its operating. You only need to press this once"



    ''' def split_bmesh_by_material(self, ob):
        #    # Get mesh of target object
        #    me = ob.data
        #    print(f'Count of mesh verts: {len(me.vertices)}')
        #
        #    # Get the number of materials assigned to the mesh
        #    mat_count = len(me.materials)
        #    print(f'Count of mesh materials: {mat_count}')
        #    # Create multiple temporary bmeshes with modifiers applied
        #    bms = []
        #
        #    # Split bmeshes by materials
        #    for mat_i in range(mat_count):
        #        bms.append(bmesh.new())
        #        bms[mat_i].from_mesh(me)
        #
        #        # Remove faces with other materials
        #        for v in bms[mat_i].verts:
        #            has_mat = False
        #            for f in v.link_faces:
        #                if f.material_index == mat_i:
        #                    has_mat = True
        #                    break
        #            if not has_mat:
        #                bms[mat_i].verts.remove(v)
        #                
        #            #if v.material_index != mat_i:
        #            #    bms[mat_i].verts.remove(v)
        #            #    
        #            #    bms[mat_i].faces.remove(f, do_flip=True)
        #
        #        # Triangulate the faces
        #        bmesh.ops.triangulate(bms[mat_i], faces=bms[mat_i].faces)
        #    new_objects = []
        #    # Create new objects for each material
        #    for bm_i in range(mat_count):
        #        new_me = bpy.data.meshes.new(name=f'Mesh_{bm_i}')
        #        bms[bm_i].to_mesh(new_me)
        #        new_ob = bpy.data.objects.new(name=f'Object_{bm_i}', object_data=new_me)
        #        bpy.context.collection.objects.link(new_ob)
        #        new_ob.location = ob.location
        #        new_objects.append(new_ob)
        #    # Free the memory
        #    for bm in bms:
        #        bm.free()
        #        
        #    return new_objects
    '''
    
    def run(self):
        
        GR = bpy.context.scene.XinMO_Folder.gameroot
        
        LoadAllModelsFromGame(
            GR,
            f"{GR}/editor/markers",
            f"{addon_path}/model_extraction_set.json"
        )
        
        # Copy from the bundled assets into the new editor/markers folder
        shutil.copytree(f"{addon_path}/assets/markers", f"{GR}/editor/markers", dirs_exist_ok=True)
        og_obj = bpy.context.object
        path = f"{GR}//editor/markers/tilemap/terrain/terrain.obj"
        
        marker_coll = bpy.data.collections["Marker_Objects_DO_NOT_EDIT"]
        if marker_coll.children.get("terrain_markers") == None:
            bpy.data.collections.new("terrain_markers")
            marker_coll.children.link(bpy.data.collections["terrain_markers"])
        mks = ["ground", "corner_outer", "corner_inner", "cliff_side_bottom", 
               "cliff_side", "cliff_blocker_upper", "cliff_side_top", 
               "cliff_blocker_lower", "cliff_blocker_lower_bottom", "cliff_blocker_lower_top"]
        regen = len(marker_coll.objects) < len(mks)
        if not regen:
            count = 0
            for ob in marker_coll.objects:
                if ob.name in mks: count+=1
            regen = count < len(mks)
        if regen:
            for ob in marker_coll.objects:
                marker_coll.objects.unlink(ob)
            bpy.ops.wm.obj_import(
                filepath=AbsPath(path), 
                forward_axis='Y', up_axis='Z',
                import_vertex_groups=True
            )
            obj = bpy.context.object
            ground_markers = marker_coll.children.get("terrain_markers")
            if ground_markers.objects.get(obj.name) == None:
                ground_markers.objects.link(obj)
                bpy.context.collection.objects.unlink(obj)

            set_modifier_node_group(obj, "FIX_LOCATION", "OrganiseTerrain")

            SelectObject(obj)

            bpy.ops.object.modifier_apply(modifier="FIX_LOCATION")
            bpy.ops.mesh.separate(type='LOOSE')

            MATtransparent = bpy.data.materials["cliff_"]
            MATcliff = bpy.data.materials["canopy_page"]
            MATground = bpy.data.materials["ground_"]

            ground = bpy.context.selected_objects[0]
            ground.name = "ground"
            ground.data.name = "ground"
            ground.data.materials.clear()
            ground.data.materials.append(MATground)
            
    
            corner_outside = bpy.context.selected_objects[1]
            corner_outside.name = "corner_outer"
            corner_outside.data.name = "corner_outer"
            corner_outside.data.materials.clear()
            corner_outside.data.materials.append(MATcliff)
            
    
            corner_inner = bpy.context.selected_objects[2]
            corner_inner.name = "corner_inner"
            corner_inner.data.name = "corner_inner"
            corner_inner.data.materials.clear()
            corner_inner.data.materials.append(MATcliff)
            
    
            cliff_side_bottom = bpy.context.selected_objects[3]
            cliff_side_bottom.name = "cliff_side_bottom"
            cliff_side_bottom.data.name = "cliff_side_bottom"
            cliff_side_bottom.data.materials.clear()
            cliff_side_bottom.data.materials.append(MATtransparent)
            
    
            cliff_side = bpy.context.selected_objects[4]
            cliff_side.name = "cliff_side"
            cliff_side.data.name = "cliff_side"
            cliff_side.data.materials.clear()
            cliff_side.data.materials.append(MATcliff)
            
    
            cliff_blocker_upper = bpy.context.selected_objects[5]
            cliff_blocker_upper.name = "cliff_blocker_upper"
            cliff_blocker_upper.data.name = "cliff_blocker_upper"
            cliff_blocker_upper.data.materials.clear()
            cliff_blocker_upper.data.materials.append(MATcliff)
            
    
            cliff_side_top = bpy.context.selected_objects[6]
            cliff_side_top.name = "cliff_side_top"
            cliff_side_top.data.name = "cliff_side_top"
            cliff_side_top.data.materials.clear()
            cliff_side_top.data.materials.append(MATcliff)
            
    
            cliff_blocker_lower = bpy.context.selected_objects[7]
            cliff_blocker_lower.name = "cliff_blocker_lower"
            cliff_blocker_lower.data.name = "cliff_blocker_lower"
            cliff_blocker_lower.data.materials.clear()
            cliff_blocker_lower.data.materials.append(MATcliff)
            
    
            cliff_blocker_lower_bottom = bpy.context.selected_objects[8]
            cliff_blocker_lower_bottom.name = "cliff_blocker_lower_bottom"
            cliff_blocker_lower_bottom.data.name = "cliff_blocker_lower_bottom"
            cliff_blocker_lower_bottom.data.materials.clear()
            cliff_blocker_lower_bottom.data.materials.append(MATtransparent)

            cliff_blocker_lower_top = bpy.context.selected_objects[9]
            cliff_blocker_lower_top.name = "cliff_blocker_lower_top"
            cliff_blocker_lower_top.data.name = "cliff_blocker_lower_top"
            cliff_blocker_lower_top.data.materials.clear()
            cliff_blocker_lower_top.data.materials.append(MATcliff)
            
            ground.hide_set(True)
            corner_outside.hide_set(True)
            corner_inner.hide_set(True)
            cliff_side_bottom.hide_set(True)
            cliff_side.hide_set(True)
            cliff_blocker_upper.hide_set(True)
            cliff_side_top.hide_set(True)
            cliff_blocker_lower.hide_set(True)
            cliff_blocker_lower_bottom.hide_set(True)
            cliff_blocker_lower_top.hide_set(True)
            
        # Time to try to export a whole layout nif to an obj
        
        #nifpath = "D:/SteamLibrary/steamapps/common/Oddworld Munchs Oddysee/layout/region00/room01/room01_bv.nif"
        #outname = "test01"
        #outpath = "D:/SteamLibrary/steamapps/common/Oddworld Munchs Oddysee/editor/test"
        #NetImmerseFileParser.parser().Generate_OBJ(nifpath, outname, GR, outpath)
        
        #if og_obj != None:
        #    SelectObject(og_obj)
        
        ''' Cant remember what this was for (some old test)
            ## obj =  bpy.context.object
            ## if obj == None: return
            ## print(f"Niffing {bpy.context.object.name}")
            ## obj.data.calc_loop_triangles()
            ## print(obj.data.vertices)
            ## print(obj.data.loop_triangles)
            ## print(obj.data.polygons)
            ## print(obj.data.materials)
            ## print(obj.data.uv_layers)
            ## new_objs = self.split_bmesh_by_material(obj)
            ## 
            ## # GOAL: Generate NIF File
            ## # Seperate mesh by materials
            ## # Export it
            ## # Rejoin mesh
            ## data = {
            ##     "header" : {
            ##         "Header" : "NetImmerse File Format, Version 3.3.0.13",
            ##         "Version" : [3,3,0,13],
            ##         "Num Blocks" : 0
            ##     },
            ##     "Block List" : []
            ## }
            ## for ob in new_objs:
            ##     pass
        '''
        

    def draw(self, context):
        layout = self.layout

    def execute(self, context):
        self.run()
        return {'FINISHED'}

class ExportXinTagsOperator(Operator):
    """Exports all objects under the 'markers' collection as Tags in the 'generatedtags.xml' file"""
    bl_idname = "wm.exportxintags"
    bl_label = "Export Markers"
    bl_description = "Exports all objects under the 'MARKERS' collection as Tags in the 'generatedtags.xml' file"
    
    def Export_Markers(self):
        print("Exporting Markers")
        xinTags = []
        print("Regenerate GUIDS")
        regenerateGUIDs()
        markers = sorted(bpy.data.collections["MARKERS"].all_objects, key=lambda o: o.XinGUID.value)
        print(markers)
        failedgeneration = []
        
        for obj in markers:
            # get wether XinObject is an actor/camera/scripttrigger etc
            obj_name = obj.name.split('.')[0].split(' ')[0]
            # Ignore non Tag Types
            if obj.XinTagType in ["none", "launchdest", "rejectdest", "shadow"]: continue
            
            print(f"Exporting {obj.name} -> {obj.XinTagType}")
            if not obj.XinGUID.hasGUID:
                LOG(f"[EXPORT] {obj_name} has no guid. ({obj})", True)
            else:
                LOG(f"[EXPORT] exporting {obj_name} as {obj.XinGUID.value}. (Object: {obj})", True)
            
            #TEST HACK
            #if obj.XinGUID.value != 100000: continue
            
            print(f"XinTag obj_name: Type -> {obj.XinTagType}")
            match(obj.XinTagType):
                case "actor":               xinTags.append(f"    {obj.XinActor.generate(obj)}\n".replace("'", '"')               )
                case "waypoint":            xinTags.append(f"    {obj.XinWaypoint.generate(obj)}\n".replace("'", '"')            )
                case "camera":              xinTags.append(f"    {obj.XinCamera.generate(obj)}\n".replace("'", '"')              )
                case "cameratransition":    xinTags.append(f"    {obj.XinCameraTransition.generate(obj)}\n".replace("'", '"')    )
                case "scripttrigger":       xinTags.append(f"    {obj.XinScriptTrigger.generate(obj)}\n".replace("'", '"')       )
                case "layouttransition":    xinTags.append(f"    {obj.XinLayoutTransition.generate(obj)}\n".replace("'", '"')    )
                case "ambiance":            xinTags.append(f"    {obj.XinAmbiance.generate(obj)}\n".replace("'", '"')            )
                case "navpath":             xinTags.append(f"    {obj.XinNavPath.generate(obj)}\n".replace("'", '"')             )
        
        f = open("./generatedTags.xml", 'w')
        f.writelines(xinTags)
        f.close()
        print("Failed:", failedgeneration)
        pass

    def draw(self, context):
        layout = self.layout

    def execute(self, context):
        LOG("Xin Tags Exporting")
        self.Export_Markers()
        return {'FINISHED'}
def BREAK():
    return input("Breaking Press Enter To Continue\nType exit to return: ")

exportindex = 0
def nextindex():
    global exportindex
    exportindex += 1
    return exportindex -1
class ExportGeo(Operator):
    bl_idname = "wm.exportgeo"
    bl_label = "Export Geo"
    bl_description = "Exports the selected object to the NIF format supported by the game"
    
    def export(self, context):
        global exportindex
        print("Beginning Export Geo")
        paths = bpy.context.scene.XinMO_Folder
        if not os.path.exists(paths.outputpath): return {'CANCELLED'}
        if paths.regionname == "": return {'CANCELLED'}
        if paths.levelname == "": return {'CANCELLED'}

        CreateFolder(f"{paths.outputpath}/{paths.regionname}/{paths.levelname}/textures")
        
        print("Made it past folder creation")
        original_active = bpy.context.view_layer.objects.active
        original_selected = [x for x in bpy.context.selected_objects]
        original_mode = bpy.context.object.mode if bpy.context.object else None

        rootindex = 0
        zbufferindex = 1
        ignorevertexcolorindex = 2
        emmisivevertexcolorsindex = 3

        visualsindex = 4
        collisoinrootindex = 5
        navcollisionrootindex = 6
        
        # reset the global index
        exportindex = 7

        # This object is used to store the blocks so it is easier to assign the indices when building the nif file
        # as in the nif file blocks point to other blocks via their index in the block list
        # it is not purley hierarchal, although it can be displayed as such, See nifskope
        indices = {
            "materials" : {},
            "textures" : {},
            "sourcetextures" : {},
            "alphaproperties" : {},
            "texturings" : {},
            "trishapes" : {},
            "shapes" : {}
        }

        # all work should be done on an copy of the object and not the actual object then that copy be deleted
        
        print("made it to object collecting for INDICIES")
        ##### START #####
        ## INDICES ##
        geo_coll = bpy.data.collections.get("LEVEL")

        all_copies = [[ x.name, x.users_collection[0], x.copy() ] for x in geo_coll.all_objects if x.XinVisGeo or x.XinColGeo or x.XinNavGeo]
        if len(all_copies) == 0: return {"CANCELLED"}
        for x in bpy.context.selected_objects:
            x.select_set(False)
        #bpy.context.selected_objects.clear() # Clear the original object selection
        for x in all_copies:
            x[2].data = x[2].data.copy()
            x[1].objects.link(x[2])
            x[2].select_set(True)
        pp_obj = all_copies[0][2]
        bpy.context.view_layer.objects.active = all_copies[0][2]
        print(f"Selected Coppies")
        print("Selected Objects:", bpy.context.selected_objects)
        
        #pp_obj.select_set(True)

        if pp_obj.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')

        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type='MATERIAL')
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action="SELECT")
        print(f"Seperated By Material")
        #print("Selected Objects:", bpy.context.selected_objects)
        bpy.ops.mesh.separate(type='LOOSE')
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action="SELECT")
        print(f"Seperated By Loose Parts")
        #print("Selected Objects:", bpy.context.selected_objects)
        bpy.ops.mesh.quads_convert_to_tris()
        bpy.ops.mesh.edge_split()
        print(f"Split faces by face edges")

        # Restore original mode and selection
        bpy.ops.object.mode_set(mode='OBJECT')
        
        def prep_object(obj, indices, paths):
            # Store current context
            
            # ORDER 
            # material prop 1
            # sourcetextures 2
            # texturing prop 3
            # last = ifexist alphaprop 4 else 3
            # trishapedata last + 1
            # trishape last + 2
            
            if obj.XinVisGeo:
                material = obj.data.materials[0]
                if not material.name in indices["materials"].keys(): indices["materials"][material.name] = nextindex()
                if not material.name in indices["textures"].keys():
                    filename = material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].links[0].from_node.image.name
                    filepath = AbsPath(material.node_tree.nodes["Principled BSDF"].inputs["Base Color"].links[0].from_node.image.filepath)
                    CreateFolder(f"{paths.outputpath}/{paths.regionname}/{paths.levelname}/textures")
                    Hardlink(filepath, f"{paths.outputpath}/{paths.regionname}/{paths.levelname}/textures/{filename}")
                    indices["textures"][material.name] = f"./../layout/{paths.regionname}/{paths.levelname}/textures/{filename}"
                if not material.name in indices["sourcetextures"].keys(): indices["sourcetextures"][material.name] = nextindex()
                if not material.name in indices["texturings"].keys(): indices["texturings"][material.name] = nextindex()
                if not material.name in indices["alphaproperties"].keys():
                    if len(material.node_tree.nodes["Principled BSDF"].inputs["Alpha"].links)>0:
                        indices["alphaproperties"][material.name] = nextindex()
            if not obj.name in indices["trishapes"].keys():  indices["trishapes"][obj.name] = nextindex()
            if not obj.name in indices["shapes"].keys():  indices["shapes"][obj.name] = nextindex()
        all_objects = [x for x in bpy.context.selected_objects]

        # More copying because i dont want 2 shapes pointing to the same shapedata
        visual_objects     = []
        for x in all_objects:
            if x.XinVisGeo:
                xx = x.copy()
                xx.data = x.data.copy()
                visual_objects.append(xx)
        navigation_objects = []
        for x in all_objects:
            if x.XinNavGeo:
                xx = x.copy()
                xx.data = x.data.copy()
                navigation_objects.append(xx)
        collision_objects  = [] 
        for x in all_objects:
            if x.XinColGeo:
                xx = x.copy()
                xx.data = x.data.copy()
                collision_objects.append(xx)
        prep_objects = []
        prep_objects.extend(visual_objects)
        prep_objects.extend(collision_objects)
        prep_objects.extend(navigation_objects)
        
        for x in prep_objects:
            print("Prepping", x)
            obj = x
            if prep_object(obj, indices, paths) == "exit": return {"CANCELLED"}
            print("Num Triangles", len(obj.data.polygons))
        print(indices)
        ## NIF DATA ##
        print("made it to NIF DATA creation")
        blocks = []
        ROOT = {
            "Block Type" : [6,b"NiNode"],
            "block" : {
                "Name" : [10,b"SCENE_ROOT"],
                "Extra Data" : -1,
                "Controller" : -1,
                "Flags" : 12,
                "Translation" : [0.0,0.0,0.0],
                "Rotation" : [[1.0,0.0,0.0],[0.0,1.0,0.0],[0.0,0.0,1.0]],
                "Scale" : 1.0,
                "Velocity" : [0.0,0.0,0.0],
                "Num Properties" : 2,
                "Properties" : [zbufferindex, ignorevertexcolorindex],
                "Has Bounding Volume" : 0,
                "Num Children" : 3,
                "Children" : [visualsindex,collisoinrootindex,navcollisionrootindex],
                "Num Effects" : 0,
                "Effects" : []
            }}
        blocks.append(ROOT)
        print("created ROOT")
        ZBUFF = {
            "Block Type" : [17,b"NiZBufferProperty"],
            "block" : {
                "Name" : [5,b"ZBuff"],
                "Extra Data" : -1,
                "Controller" : -1,
                "Flags" : 3
            }}
        blocks.append(ZBUFF)
        print("created ZBUFF")
        IgnoreVC = {
            "Block Type" : [21,b"NiVertexColorProperty"],
            "block" : {
                "Name" : [9,b"Ignore_VC"],
                "Extra Data" : -1,
                "Controller" : -1,
                "Flags" : 0,
                "Vertex Mode" : 0,
                "Lighting Mode" : 1
            }}
        blocks.append(IgnoreVC)
        print("created IgnoreVC")
        EmmisiveVC = {
            "Block Type" : [21,b"NiVertexColorProperty"],
            "block" : {
                "Name" : [11,b"Emmisive_VC"],
                "Extra Data" : -1,
                "Controller" : -1,
                "Flags" : 0,
                "Vertex Mode" : 1,
                "Lighting Mode" : 1
            }}
        blocks.append(EmmisiveVC)
        print("created EmmisiveVC")
        VIS_ROOT = {
            "Block Type" : [6,b"NiNode"],
            "block" : {
                "Name" : [13,b"*VISUALS_ROOT"],
                "Extra Data" : -1,
                "Controller" : -1,
                "Flags" : 12,
                "Translation" : [0.0,0.0,0.0],
                "Rotation" : [[1.0,0.0,0.0],[0.0,1.0,0.0],[0.0,0.0,1.0]],
                "Scale" : 1.0,
                "Velocity" : [0.0,0.0,0.0],
                "Num Properties" : 0,
                "Properties" : [],
                "Has Bounding Volume" : 0,
                "Num Children" : 0,
                "Children" : [],
                "Num Effects" : 0,
                "Effects" : []
            }}
        blocks.append(VIS_ROOT)
        print("created VIS ROOT")
        COLL_ROOT = {
            "Block Type" : [6,b"NiNode"],
            "block" : {
                "Name" : [15,b"*COLLISION_ROOT"],
                "Extra Data" : -1,
                "Controller" : -1,
                "Flags" : 13,
                "Translation" : [0.0,0.0,0.0],
                "Rotation" : [[1.0,0.0,0.0],[0.0,1.0,0.0],[0.0,0.0,1.0]],
                "Scale" : 1.0,
                "Velocity" : [0.0,0.0,0.0],
                "Num Properties" : 0,
                "Properties" : [],
                "Has Bounding Volume" : 0,
                "Num Children" : 0,
                "Children" : [],
                "Num Effects" : 0,
                "Effects" : []
            }}
        blocks.append(COLL_ROOT)
        print("created COLL ROOT")
        NAV_ROOT = {
            "Block Type" : [6,b"NiNode"],
            "block" : {
                "Name" : [18,b"*NAVCOLLISION_ROOT"],
                "Extra Data" : -1,
                "Controller" : -1,
                "Flags" : 13,
                "Translation" : [0.0,0.0,0.0],
                "Rotation" : [[1.0,0.0,0.0],[0.0,1.0,0.0],[0.0,0.0,1.0]],
                "Scale" : 1.0,
                "Velocity" : [0.0,0.0,0.0],
                "Num Properties" : 0,
                "Properties" : [],
                "Has Bounding Volume" : 0,
                "Num Children" : 0,
                "Children" : [],
                "Num Effects" : 0,
                "Effects" : []
            }}
        blocks.append(NAV_ROOT)
        print("created NAV ROOT")

        
        
        def FixArray(array):
            if len(array) == 1: return array[0]
            return array
        def FixNiNodeArrays(ninode):
            ninode["block"]["Properties"] = FixArray(ninode["block"]["Properties"])
            ninode["block"]["Children"] = FixArray(ninode["block"]["Children"])
            ninode["block"]["Effects"] = FixArray(ninode["block"]["Effects"])
            
        print("made it to object collection 2 (seperate into geo types)")
        print("Beginning Object Parsing")
        # These are so i can just read what it means an not think about it
        def LAST_INDEX(): return len(blocks)-1
        def CURRENT_INDEX(): return len(blocks)
        
        
        class GeoType(Enum):
            VISUAL = 0
            COLLISION = 1
            NAV_COLLISION = 3


        def parseobject(obj, blocks, ROOT, geotype:int):
                print("[Parsing] Is Vis Check")
                if geotype == GeoType.VISUAL:
                    material = obj.data.materials[0]
                    Mat = {
                        "Block Type" : [18,b"NiMaterialProperty"],
                        "block" : {
                            "Name" : [len(f"{material.name}_MT"),f"{material.name}_MT".encode("utf-8")],
                            "Extra Data" : -1,
                            "Controller" : -1,
                            "Flags" : 1,
                            "Ambient Color" : material.diffuse_color,
                            "Diffuse Color" : material.diffuse_color,
                            "Specular Color" : material.specular_color,
                            "Emissive Color" : material.node_tree.nodes["Principled BSDF"].inputs["Emission Color"].default_value,
                            "Glossiness" : int(1 - material.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value * 100),
                            "Alpha" : int(material.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value)
                        }}
                    if LAST_INDEX() < indices["materials"][material.name]:
                        print("Adding Mat to block",CURRENT_INDEX(), Mat)
                        blocks.append(Mat)
                        print("created Mat")
                    else:
                        print("Mat already in block", Mat)
                    ROOT["block"]["Properties"].append(indices["materials"][material.name])
                    ST = {
                        "Block Type" : [15, b"NiSourceTexture"],
                        "block" : {
                        "Name" : [len(f"{material.name}_ST"),f"{material.name}_ST".encode("utf-8")],
                        "Extra Data" : -1,
                        "Controller" : -1,
                        "Use External" : 1,
                        "File Name" : [len(indices["textures"][material.name]), indices["textures"][material.name].encode("utf-8")],
                        "Format Prefs" : {
                            "Pixel Layout" : 5,
                            "Use Mipmaps" : 2,
                            "Alpha Format" : 3 },
                        "Is Static" : 1
                        }}
                    
                    if LAST_INDEX() < indices["sourcetextures"][material.name]:
                        print("Adding ST to block",CURRENT_INDEX(), ST)
                        blocks.append(ST)
                        print("created ST")
                    else:
                        print("ST already in block", ST)
                    ROOT["block"]["Properties"].append(indices["sourcetextures"][material.name])
    
                    TexturingProperty = {
                        "Block Type" : [19,b"NiTexturingProperty"],
                        "block" : {
                            "Name" : [len(f"{material.name}_TP"),f"{material.name}_TP".encode("utf-8")],
                            "Extra Data" : -1,
                            "Controller" : -1,
                            "Flags" : 0,
                            "Apply Mode" : 2,
                            "Texture Count" : 1,
                            "Has Base Texture" : 1,
                            "Base Texture" : {
                                "Source" : indices["sourcetextures"][material.name],
                                "Clamp Mode" : 3,
                                "Filter Mode" : 2,
                                "UV Set" : 0,
                                "PS2 L" : 0,
                                "PS2 K" : -75,
                                "unknown Short 1" : 0
                                },
                            "Has Dark Texture" : 0,
                            "Has Detail Texture" : 0,
                            "Has Gloss Texture" : 0,
                            "Has Glow Texture" : 0
                        }}
                    
                    if LAST_INDEX() < indices["texturings"][material.name]:
                        print("Adding TexturingProperty to block",CURRENT_INDEX(), TexturingProperty)
                        blocks.append(TexturingProperty)
                        print("created TexturingProperty")
                    else:
                        print("TexturingProperty already in block", TexturingProperty)
                    ROOT["block"]["Properties"].append(indices["texturings"][material.name])
                    
                    if material.name in indices["alphaproperties"].keys():
                        AlphaProperty = {
                            "Block Type" : [15,b"NiAlphaProperty"],
                            "block" : {
                                "Name" : [len(material.name), material.name.encode("utf-8")],
                                "Extra Data" : -1,
                                "Controller" : -1,
                                "Flags" : 13037,
                                "Threshold" : 64
                            }}
                        if LAST_INDEX() < indices["alphaproperties"][material.name]:
                            print("Adding AlphaProperty to block",CURRENT_INDEX(), AlphaProperty)
                            blocks.append(AlphaProperty)
                            print("created AlphaProperty")
                        else:
                            print("AlphaProperty is already in block")
                        ROOT["block"]["Properties"].append(indices["alphaproperties"][material.name])
    
                TriShapeData = {
                "Block Type" : [14,b"NiTriShapeData"],
                "block" : {
                    "Num Vertices" : len(obj.data.vertices),
                    "Has Vertices" : 1,
                    "Vertices" : [list(obj.matrix_world @ x.co) for x in obj.data.vertices],
                    "Has Normals" : 1,
                    "Normals" : [list(x.normal) for x in obj.data.vertices]
                    }}
                cen = Vector()
                for v in obj.data.vertices: cen += v.co
                cen /= len(obj.data.vertices)
                max_dist = 0
                for v in obj.data.vertices:
                    dist = (v.co - cen).length
                    if dist > max_dist: max_dist = dist
                TriShapeData["block"]["Bounding Sphere"] = {
                    "Center" : cen,
                    "Radius" : max_dist
                }
                TriShapeData["block"]["Has Vertex Colors"] = obj.data.attributes.get("Vertex Colors") is not None
                if TriShapeData["block"]["Has Vertex Colors"]:
                    TriShapeData["block"]["Vertex Colors"] = [list(x.color) for x in obj.data.color_attributes["Vertex Colors"].data]
                TriShapeData["block"]["Data Flags"] = len(obj.data.uv_layers)
                TriShapeData["block"]["Has UV"] = TriShapeData["block"]["Data Flags"]
                if TriShapeData["block"]["Has UV"]:
                    TriShapeData["block"]["UV Sets"] = []
                    for uv_layer in obj.data.uv_layers:
                        uvs = []
                        for loop in obj.data.loops:
                            uvs.append(uv_layer.data[loop.index].uv[:])
                        TriShapeData["block"]["UV Sets"].append(uvs)
                    #############
                    ############TODO Fix the UV Bug (Uvs are wierd in Nifskope and they dont show up properly so something is wrong witht the format here and needs fixing)
                    #############
                    #    [ 
                    #        [ uv[1].vector[0],uv[1].vector[1]*-1] for uv in layer.uv.items() 
                    #    ] for layer in obj.data.uv_layers
                    #]
                    print(TriShapeData["block"]["UV Sets"][0][0], len(TriShapeData["block"]["UV Sets"][0]))
                TriShapeData["block"]["Num Triangles"] = len(obj.data.polygons)
                TriShapeData["block"]["Num Triangle Points"] = int(TriShapeData["block"]["Num Triangles"] * 3)
                TriShapeData["block"]["Triangles"] = [list(x.vertices) for x in obj.data.polygons]
                print("Num Triangles", len(obj.data.polygons))
                mgs = []
                for i in range(len(obj.data.vertices)):
                    mg = {
                            "Num Vertices" : 0, 
                            "Vertex Indices" : [] 
                        }
                    for j in range(len(obj.data.vertices)):
                        if obj.data.vertices[i].normal == obj.data.vertices[j].normal:
                            mg["Num Vertices"] += 1
                            mg["Vertex Indices"].append(j)
                    if mg["Num Vertices"] == 1:
                        mg["Vertex Indices"] = mg["Vertex Indices"][0]
                    mgs.append(mg)
                TriShapeData["block"]["Num Match Groups"] = len(mgs)
                TriShapeData["block"]["Match Groups"] = mgs
                print("Adding TriShapeData to block",CURRENT_INDEX())
                blocks.append(TriShapeData)
                ROOT["block"]["Properties"].append(indices["trishapes"][obj.name])
                print("created TriShapeData")

                TriShape = {
                    "Block Type" : [10,b"NiTriShape"],
                    "block" : {
                        "Name" : [len(obj.name), obj.name.encode("utf-8")],
                        "Extra Data" : -1,
                        "Controller" : -1,
                        "Flags" : 4,
                        "Translation" : [0.0,0.0,0.0],
                        "Rotation" : [[1.0,0.0,0.0],[0.0,1.0,0.0],[0.0,0.0,1.0]],
                        "Scale" : 1.0,
                        "Velocity" : [0.0,0.0,0.0]
                    }}
                np = 0
                if geotype == GeoType.VISUAL:
                    np+=3 # Zbuffer, Texturing, Material (if VisGeo)
                    if getattr(indices["alphaproperties"], material.name, None) is not None: np+=1
                    if obj.data.attributes.get("Vertex Colors") is not None: np += 1
                TriShape["block"]["Num Properties"] = np
                props = []
                if geotype == GeoType.VISUAL:
                    props.extend([zbufferindex, indices["texturings"][material.name], indices["materials"][material.name]])
                    if getattr(indices["alphaproperties"], material.name, None) is not None: props.append(indices["alphaproperties"][material.name])
                    if obj.data.attributes.get("Vertex Colors") is not None: props.append(emmisivevertexcolorsindex)
                TriShape["block"]["Properties"] = props
                TriShape["block"]["Has Bounding Volume"] = 0
                TriShape["block"]["Data"] = indices["trishapes"][obj.name]
                TriShape["block"]["Skin Instance"] = -1
                print("Adding TriShape to block",CURRENT_INDEX(), TriShape)
                blocks.append(TriShape)
                ROOT["block"]["Num Children"] += 1
                ROOT["block"]["Children"].append(indices["shapes"][obj.name])
                print("created TriShape")
        print("Creating Visuals")
        for obj in visual_objects: parseobject(obj, blocks, VIS_ROOT, GeoType.VISUAL)
        print(VIS_ROOT)
        FixNiNodeArrays(VIS_ROOT)
        print(VIS_ROOT)
        
        print("Creating Collisions")
        for obj in collision_objects: parseobject(obj, blocks, COLL_ROOT, GeoType.COLLISION)
        FixNiNodeArrays(COLL_ROOT)
        
        print("Creating Nav Collisions")
        for obj in navigation_objects: parseobject(obj, blocks, NAV_ROOT, GeoType.NAV_COLLISION)
        FixNiNodeArrays(NAV_ROOT)

        #num_blocks = len(blocks)
        ## HEADER ##
        headerblock = {
            "Header" : b"NetImmerse File Format, Version 3.3.0.13",
            "Version" : mylist([3,3,0,13]),
            "Num Blocks" : len(blocks)
        }
        print("created header")
        footerblock = {}
        footerblock["Num Roots"] = 1
        footerblock["Roots"] = 0

        print("created footer")
        nif = NetImmerseFileParser.parser()
        nif.data = {
            "header" : headerblock,
            "Block List" : blocks,
            "footer" : footerblock
        }
        print("created nif")

        nif.save(f"{paths.outputpath}/{paths.regionname}/{paths.levelname}/{paths.levelname}.nif")
        print(f"saved nif to {paths.outputpath}/{paths.regionname}/{paths.levelname}/{paths.levelname}.nif")

        ## CLEANUP ##
        #for x in visual_objects: bpy.data.objects.remove(x[2], do_unlink=True)
        #for x in navigation_objects: bpy.data.objects.remove(x[2], do_unlink=True)
        #for x in collision_objects: bpy.data.objects.remove(x[2], do_unlink=True)
        
        for obj in bpy.context.selected_objects:
            #bpy.data.meshes.remove(obj.data, do_unlink=True)
            bpy.data.objects.remove(obj, do_unlink=True)
        for x in all_copies:
            if not str(x[2]) == "<bpy_struct, Object invalid>":
                bpy.data.objects.remove(x[2], do_unlink=True)
            
        print("Original Selected:", original_selected)
        for obj in original_selected:
            obj.select_set(True)
        print("Original Active:", original_active)
        if original_active: bpy.context.view_layer.objects.active = original_active
        elif len(original_selected) > 0: bpy.context.view_layer.objects.active = original_selected[0]
        print("Original Mode:", original_mode)
        if original_mode: bpy.ops.object.mode_set(mode=original_mode)
        
        return {'FINISHED'}
        
    
    def draw(self, context):
        layout = self.layout
    def execute(self, context):
        result = self.export(context)
        return result
    
class UpdateModelsOperator(Operator):
    """Exports all objects under the 'markers' collection as Tags in the 'generatedtags.xml' file"""
    bl_idname = "wm.updatemodels"
    bl_label = "Update Selected Model"
    bl_description = "Update the model for the selected marker (do this after renaming the marker with an actor name)"
    
    def update_models(self):
        
        ctx = bpy.context
        ctx.object.XinMeshController.update_mesh(ctx)
        
        #for obj in objs:
        #    if not isMarker(obj): return

        #    match(obj.name.split('.')[0].split(' ')[0]):
        #        case "mudokon": obj.XinMudokonAnimationTag.variant_update(bpy.context)
        #        case "door":    obj.XinDoor.update_mesh(bpy.context)
        #        case "munch":   obj.data = bpy.data.meshes["gabbit_munch"]
        #        case "door":    obj.XinDoor.update_mesh(bpy.context)
        #        case "ladder":  obj.data = bpy.data.meshes["ladder"]
        #        case "lever360":  obj.data = bpy.data.meshes["lever360"]
        #        case "dynamiclight":
        #            diff = obj.XinDynamicLight.diffusecolor
        #            obj.XinDynamicLight.diffusecolor[0] = min(diff[0], 1.0)
        #            obj.XinDynamicLight.diffusecolor[1] = min(diff[1], 1.0)
        #            obj.XinDynamicLight.diffusecolor[2] = min(diff[2], 1.0)
        #            spec = obj.XinDynamicLight.specularcolor
        #            obj.XinDynamicLight.specularcolor[0] = min(spec[0], 1.0)
        #            obj.XinDynamicLight.specularcolor[1] = min(spec[1], 1.0)
        #            obj.XinDynamicLight.specularcolor[2] = min(spec[2], 1.0)
        #            amb = obj.XinDynamicLight.ambientcolor
        #            obj.XinDynamicLight.ambientcolor[0] = min(amb[0], 1.0)
        #            obj.XinDynamicLight.ambientcolor[1] = min(amb[1], 1.0)
        #            obj.XinDynamicLight.ambientcolor[2] = min(amb[2], 1.0)
        #            obj.XinDynamicLight.radius = obj.scale.x
        #            if ["point","spot"].__contains__(obj.XinDynamicLight.lighttype):
        #                obj.XinDynamicLight.lightshape = "none"
        #            obj.XinDynamicLight.update_model(obj)
        #        case "well": obj.XinWell.update_model(obj)
        #        case "meep": obj.XinMeep.update_model(obj)
        #        case "resurrectiontotem": obj.XinResurrectionTotem.update_model(obj)
    
    def draw(self, context):
        layout = self.layout

    def execute(self, context):
        LOG("UpdatingModels")
        self.update_models()
        return {'FINISHED'}

class LoadRegion(Operator):
    bl_idname = "wm.loadregion"
    bl_label = "Load Region (Level)"
    bl_description = "Load the region specified in the text field above"
    
    def LoadRegion(self):
        # PRE REQUISITES 
        # Each Tag Class (Finished: Actor, )
        # Some Load Level UI (need filpath text field)
        # 
        # 
        
        # REGION FILE (xrg)
        # * Read the filepath in the text box
        # * Test validity
        # * Create the Region Object to hold the region file data and add the data
        # * replace './..' with the game root folder in the zone path
        # * Load the zone
        
        # ZONE FILE (xin)
        # * Create Zone object
        # * Set attibutes of the Zone object
        # * Create Settings object
        # * Set the attributes of the settings object
        # * Create the Include object
        # * Append the list in the Include object with the loaded includes
        # * Loop through the taglist adding each tag to the scene and updating their models to reflect their data
        
        # FOR EACH TAG
        # * setup attributes
        # * setup components
        # * apply guid loaded from file
        # * update scene model to reflect the state of the tag
        # * When adding to the scene add to a collection named based on the tags type 
        #   (actor, waypoint, camera, cameratransition, etc) as to group them and not 
        #   make it unbearable to search through
        #   
        
        
        pass
    
    def draw(self, context):
        layout = self.layout
        pass
    
    def execute(self, context):
        LOG("Loading Region")
        self.LoadRegion()
        return {'FINISHED'}

""" Preset Xin marker Operators """

""" menu """

class Xin_Add_Marker(Operator):
    bl_idname = "motm.addmarker"
    bl_label = "Add Marker"

    tagtype : StringProperty(name="Tag Type", description="", default="")
    actortype : StringProperty(name="Actor Type", description="", default="")

    def execute(self, context):
        bpy.ops.mesh.primitive_cube_add(size=1, enter_editmode=False, align='WORLD', location=bpy.context.scene.cursor.location, scale=(1,1,1))
        obj = bpy.context.object
        obj.XinTagType = self.tagtype
        obj.name = self.tagtype
        obj.XinActor.type = self.actortype
        bpy.context.collection.objects.unlink(obj)
        bpy.data.collections["Markers"].objects.link(obj)
        return {'FINISHED'}

def AddMarkerEntry(layout, displayname, tagtype, actortype):
    op = layout.operator(Xin_Add_Marker.bl_idname, text=displayname)
    op.tagtype = tagtype
    op.actortype = actortype

class AddMunchMaker_characters(Menu):
    bl_idname = "MOTM_MT_munch_markers_characters"
    bl_label = "Characters"

    def draw(self, context):
        layout = self.layout
        AddMarkerEntry(layout, "Munch","actor","munch")
        AddMarkerEntry(layout, "Fuzzle","actor","fuzzle")
        AddMarkerEntry(layout, "Mudokon","actor","mudokon")
        AddMarkerEntry(layout, "Shaman","actor","shaman")
        AddMarkerEntry(layout, "Paramite","actor","paramite")
        AddMarkerEntry(layout, "Scrab","actor","scrab")
        AddMarkerEntry(layout, "Meep","actor","meep")
        AddMarkerEntry(layout, "Slog","actor","slog")
        AddMarkerEntry(layout, "Slig","actor","slig")
        AddMarkerEntry(layout, "Big Bro","actor","bigbro")
        AddMarkerEntry(layout, "Glukkon","actor","glukkon")
        AddMarkerEntry(layout, "Intern","actor","intern")
        AddMarkerEntry(layout, "Vykker","actor","vykker")
        AddMarkerEntry(layout, "Snoozer","actor","candystriper")

class AddMunchMarker_interactables(Menu):
    bl_idname = "MOTM_MT_munch_markers_interactables"
    bl_label = "Interactable"

    def draw(self, context):
        layout = self.layout
        AddMarkerEntry(layout, "Ladder","actor","ladder")
        AddMarkerEntry(layout, "Rescue Portal","actor","rescueportal")
        AddMarkerEntry(layout, "Lever 360","actor","lever360")
        AddMarkerEntry(layout, "Vendo","actor","vendingmachine")
        AddMarkerEntry(layout, "Nest","actor","nest")
        AddMarkerEntry(layout, "Spooce Shrub","actor","humshrub")
        AddMarkerEntry(layout, "Foot Switch","actor","footswitch")
        AddMarkerEntry(layout, "Asset Lock","actor","assetlock")
        AddMarkerEntry(layout, "Control Panel","actor","hcranepanel")
        AddMarkerEntry(layout, "Shaman Circle","actor","shamancircle")
        AddMarkerEntry(layout, "Touch Stone","actor","touchstone")
        AddMarkerEntry(layout, "Well","actor","well")
        AddMarkerEntry(layout, "Resurrection Totum","actor","resurrectiontotem")
        AddMarkerEntry(layout, "Wheel Chair","actor","wheelchair")
        AddMarkerEntry(layout, "Crate","actor","crate")
        AddMarkerEntry(layout, "Land Mine","actor","landmine")
        AddMarkerEntry(layout, "Tethered Mine","actor","tetheredmine")
        AddMarkerEntry(layout, "Cage","actor","cage")
        AddMarkerEntry(layout, "Recycler","actor","recycler")

class AddMunchMarker_scriptables(Menu):
    bl_idname = "MOTM_MT_munch_markers_scriptables"
    bl_label = "Scriptabled"

    def draw(self, context):
        layout = self.layout
        AddMarkerEntry(layout, "Door","actor","door")
        AddMarkerEntry(layout, "Patrol Point","actor","patrolpoint")
        AddMarkerEntry(layout, "Chant Suppressor","actor","chantsuppressor")
        AddMarkerEntry(layout, "Teleporter","actor","teleporter")
        AddMarkerEntry(layout, "Spawner","actor","spawner")
        AddMarkerEntry(layout, "Crane","actor","hcrane")
        AddMarkerEntry(layout, "Water","actor","water")
        AddMarkerEntry(layout, "Lamp","actor","lamp")

class AddMunchMarker_environment(Menu):
    bl_idname = "MOTM_MT_munch_markers_environment"
    bl_label = "Environment"

    def draw(self, context):
        layout = self.layout
        AddMarkerEntry(layout, "Dynamic Light","actor","dynamiclight")
        AddMarkerEntry(layout, "Lens Flare","actor","lensflare")
        AddMarkerEntry(layout, "Texture Light","actor","texturelight")
        AddMarkerEntry(layout, "Generic Particles","actor","genericparticles")

class AddMunchMarker_other(Menu):
    bl_idname = "MOTM_MT_munch_markers_other"
    bl_label = "Other"

    def draw(self, context):
        layout = self.layout        
        AddMarkerEntry(layout, "Generic Object","actor","genericobject")
        AddMarkerEntry(layout, "Death Tag","actor","deathtag")
        AddMarkerEntry(layout, "Possessor","actor","possessor")

class AddMunchObject_Root(Menu):
    bl_idname = "MOTM_MT_munch_markers_root"
    bl_label = "Xin Templates"
    
    
    def draw(self, context):
        layout = self.layout
        layout.menu(AddMunchMaker_characters.bl_idname, text=AddMunchMaker_characters.bl_label)
        layout.menu(AddMunchMarker_interactables.bl_idname, text=AddMunchMarker_interactables.bl_label)
        layout.menu(AddMunchMarker_scriptables.bl_idname, text=AddMunchMarker_scriptables.bl_label)
        layout.menu(AddMunchMarker_environment.bl_idname, text=AddMunchMarker_environment.bl_label)
        layout.menu(AddMunchMarker_other.bl_idname, text=AddMunchMarker_other.bl_label)

class AddMunchMarker(Menu):
    bl_idname = "OBJECT_MT_add_munch_markers"
    bl_label = "Munch Xin Marker"
    
    def draw(self, context):
        layout = self.layout
        layout.separator(type="LINE")
        layout.operator(Xin_Object_add.bl_idname, text=Xin_Object_add.bl_label)
        layout.menu(AddMunchObject_Root.bl_idname, text=AddMunchObject_Root.bl_label)

    def initialise(self):
        bpy.utils.register_class(AddMunchMarker)
        pass
    def uninitialise(self):
        bpy.utils.unregister_class(AddMunchMarker)
        pass


""" Panels """
class PanelData:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'MO Tag Manager'
    #bl_context = "object"  
    #bl_options = {"DEFAULT_CLOSED"}

class MO_Folder(PropertyGroup):
    
    AU = True # prevent infinite recursion
    def update_gameroot(self, context):
        if self.AU == False: return
        self.AU = False
        self.gameroot = AbsPath(self.gameroot)
        self.AU = True

    def update_outputpath(self, context):
        if self.AU == False: return
        self.AU = False
        self.outputpath = AbsPath(self.outputpath)
        self.AU = True
        
    gameroot : StringProperty(
        name="Game Root Folder", description="The 'Oddworld Munches Oddysee' folder",
        default="", subtype="DIR_PATH",
        update=update_gameroot
    )
    
    outputpath : StringProperty(
        name="Output Folder", description="The Folder that all generated levels are stored",
        default="", subtype="DIR_PATH",
        update=update_outputpath
    )
    
    regionname : StringProperty(
        name="Region Name", description="The name of the folder the level folder will go into (Consider this your root folder for a set of levels you plan to add)",
        default=""
    )
    
    levelname : StringProperty(
        name="Level Name", description="The name of the folder the current level will be outputed into",
        default=""
    )
    
    
    
    def draw(self, layout):
        layout.prop(self, "gameroot")
        layout.prop(self, "outputpath")
        layout.prop(self, "regionname")
        layout.prop(self, "levelname")
        pass

class CreateXinScene(Operator):
    bl_idname = "motm.createxinscene"
    bl_label = "Create Xin Scene"
    bl_description = "Sets up the basic scene layout, This will wipe out any collections int the scene"

    def execute(self, context):
        
        # remove all collections
        while len(bpy.data.collections) > 0:
            bpy.data.collections.remove(bpy.data.collections[0])

        # Set up Collection Structure
        geom = bpy.data.collections.new("Geometry")
        geom.color_tag = "COLOR_03"
        bpy.context.scene.collection.children.link(geom)
        
        marks = bpy.data.collections.new("Markers")
        marks.color_tag = "COLOR_05"
        bpy.context.scene.collection.children.link(marks)

        dne = bpy.data.collections.new("Marker_Objects_DO_NOT_EDIT")
        dne.color_tag = "COLOR_01"
        bpy.context.scene.collection.children.link(dne)

        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0,0,0))
        r_sph_o = bpy.context.active_object

        bpy.context.scene.collection.objects.unlink(r_sph_o)
        dne.objects.link(r_sph_o)
        r_sph_o.hide_set(True)
        r_sph_o.name = "REJECTDEST"

        bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(0,0,0))
        l_sph_o = bpy.context.active_object
        bpy.context.scene.collection.objects.unlink(l_sph_o)
        dne.objects.link(l_sph_o)
        l_sph_o.hide_set(True)
        l_sph_o.name = "LAUNCHDEST"

        # Append modifiers from blend file in addon folder
        datafile = f"{addon_path}/assets/data.blend"
        with bpy.data.libraries.load(datafile, link=False) as (data_from, data_to):
            data_to.node_groups = data_from.node_groups
        
        for ng in bpy.data.node_groups:
            ng.use_fake_user = True
            
        # load all assets
        #bpy.ops.motm.loadallassets()

        bpy.context.scene.IsXinScene = True

        return {'FINISHED'}

class MunchesOddysee(PanelData, Panel): 
    global currenttag
    bl_idname = "MOTM_PT_munchs_oddysee_tag_manager"
    bl_label = "Munches Oddysee Tag Manager"
    
    def draw(self, context):
        layout = self.layout

        #devOBJ = bpy.types.Object(bpy.data.objects.get("DevOBJ"))
        #layout.draw(bpy.context.scene, "XinDevmode")
        #if bpy.context.scene.XinDevmode == True:
        #    layout.label(text="Dev Mode")
        #    layout.operator(RequestRandomOperator.bl_idname,text=RequestRandomOperator.bl_label)
        #    layout.label(text="Current Tag: "+str(devOBJ["currenttag"]))
        #    layout.label(text="Has Completed: " + str(devOBJ.get("hascompletedtag", True)))
        #    layout.label(text="")
        if not bpy.context.scene.IsXinScene:
            layout.operator(CreateXinScene.bl_idname, text=CreateXinScene.bl_label)
            return

        context.scene.XinMO_Folder.draw(layout)
        gp = context.scene.XinMO_Folder.gameroot
        if (
            os.path.exists(f"{gp}/Munch.exe") and
            os.path.exists(f"{gp}/bin/Launcher.exe")):

            CreateFolder(f"{gp}/editor/markers")

            layout.operator(LoadAllAssets_BTN.bl_idname, text=LoadAllAssets_BTN.bl_label)
        else:
            layout.label(text="Cant load assets, enter valid game path.")
        if os.path.exists(context.scene.XinMO_Folder.outputpath):
            layout.operator(ExportXinTagsOperator.bl_idname,text=ExportXinTagsOperator.bl_label)
            layout.operator(ExportGeo.bl_idname, text=ExportGeo.bl_label)
        
        layout.label(text="")
        #layout.operator(UpdateModelsOperator.bl_idname,text=UpdateModelsOperator.bl_label)

#class DevData(PropertyGroup):
#    
#    devmode             : BoolProperty(name = "Dev Mode", description = "Toggles the visibility of dev tools.", default = False)
#    hascompletedtag     : BoolProperty(name = "Has Completed Tag", description = "Toggles the visibility of dev tools.", default = False)
#    currenttag          : StringProperty(name = "Current Tag", description = "Toggles the visibility of dev tools.", default = "")
#
#    def draw(self, layout):
#        layout.prop(self, "devmode", toggle=True)
#        if self.devmode:
#            layout.label(text=f"Has Completed Tag: {self.hascompletedtag}")
#            layout.label(text=f"Current Tag: {self.currenttag}")
#            layout.operator(RequestRandomOperator.bl_idname, text=RequestRandomOperator.bl_label)


class XinTagsPanel(PanelData, Panel):
    bl_parent_id = "MOTM_PT_munchs_oddysee_tag_manager"
    bl_idname = "MOTM_PT_xin_tags_panel"
    bl_label = "Xin Tags"

    def draw(self, context: bpy.types.Context):
        layout = self.layout  
        obj = context.object
        
        col = layout.column(align=True)
        col.label(text="Note: Many actors will have a model that gets added by the tag.")
        col.label(text="Some are hard coded and others reference a file path.")
        col.label(text="Some include things like door, wells.")
        col.label(text="Dont press the buttons below for these actors.")
        
        row = layout.row(align=True)
        if obj:
            row.prop(obj, "XinVisGeo", toggle=1)
            row.prop(obj, "XinNavGeo", toggle=1)
            row.prop(obj, "XinColGeo", toggle=1)
            layout.row().prop(obj, "XinIgnore", toggle=1)
            layout.prop(obj, "XinTagType")
            #print("Attempting Drawing actor")
            # must be a Xin Object to continue
            valid_tagtypes = [
                "actor",
                "waypoint",
                "camera",
                "cameratransition",
                "scripttrigger",
                "layouttransition",
                "ambiance",
                "navpath",
                "editor_ground"
            ]
            if obj.XinTagType == 'none': 
                #print("isXinObject Fail")
                return
            #print("isXinObject Success")
            
            
            if obj.XinGUID.hasGUID:
                layout.label(text=f"GUID: {obj.XinGUID.value}")
            
            match(obj.XinTagType):
                case "actor": obj.XinActor.draw(layout, obj)
                case "waypoint": obj.XinWaypoint.draw(layout, obj)
                case "camera": obj.XinCamera.draw(layout, obj)
                case "cameratransition": obj.XinCameraTransition.draw(layout, obj)
                case "scripttrigger": obj.XinScriptTrigger.draw(layout, obj)
                case "layouttransition": obj.XinLayoutTransition.draw(layout, obj)
                case "ambiance": obj.XinAmbiance.draw(layout, obj)
                case "navpath": obj.XinNavPath.draw(layout, obj)
                # Special cases (attributes that have an object association)
                case "rejectdest": layout.prop(obj.parent.XinActor, "rejectdest")
                case "launchdest": layout.prop(obj.parent.XinActor, "launchdest")
                case "editor_ground" : obj.EditorGround.draw(layout, obj)
                
            # new attribute and component based layout
            
            
            
            
            # Old name based layout
            #match(obj.name.split('.')[0].split(' ')[0]):
            #    case "mudokon":             obj.XinMudokon.draw(layout, obj)
            #    case "munch":               obj.XinMunch.draw(layout, obj)
            #    case "shadow":              obj.XinShadow.draw(layout, obj)
            #    case "door":                obj.XinDoor.draw(layout, obj)
            #    case "ladder":              obj.XinLadder.draw(layout, obj)
            #    case "lever360":            obj.XinLever360.draw(layout, obj)
            #    case "dynamiclight":        obj.XinDynamicLight.draw(layout, obj)
            #    case "well":                obj.XinWell.draw(layout, obj)
            #    case "meep":                obj.XinMeep.draw(layout, obj)
            #    case "resurrectiontotem":   obj.XinResurrectionTotem.draw(layout, obj)

""" Functions """
def isMarker(obj):
    isIn = False
    markers = bpy.types.Collection(bpy.data.collections.get("markers")).all_objects
    for marker in markers:
        if marker.name == obj.name: 
            isIn = True
            break
    if not isIn: return False
    return True

def get_object_dat(name:str):
    for obj in bpy.data.objects:
        if(obj.name is name): return obj.data
    return None

def breakline(layout):
    layout.label(text="")
    

def genTransform(obj:bpy.types.Object):
    return f'position="{genPos(obj.location)}" rotation="{genRot([obj.rotation_euler.x, obj.rotation_euler.y, obj.rotation_euler.z])}"'

def genPos(loc:mathutils.Vector):
    return f"{round(loc.x, 3)},{round(loc.y, 3)},{round(loc.z, 3)}"


def genRot(rotarr: bpy.types.bpy_prop_array):
    
    euler_as_degrees = [ angle * 180 / math.pi for angle in rotarr]
    
    return f"{round(euler_as_degrees[0],3)},{round(euler_as_degrees[1],3)},{round(euler_as_degrees[2],3)*-1}"

def genShadow(cguid):
    markers = bpy.types.Collection(bpy.data.collections.get("markers")).all_objects
    shadow = bpy.types.Object(markers.get("shadow"))
    return f'<shadow componentguid="{cguid}" method="{shadow.XinShadow.method}" opacity="{shadow.XinShadow.opacity}" direction="{genPos(shadow.location)}" maxshadows="{shadow.XinShadow.maxshadows}"/>'

def getOrCreateChildObject(
    objname : str, 
    obj: bpy.types.Object, 
    material_name: str,
    position):
    childobj = [x for x in obj.children if x.name.__contains__(objname)]        
    created = False
    if len(childobj) == 0:
        #create new object
        created = True
        if bpy.types.Material(bpy.data.materials.get(material_name)) == None:
            print(f"Failed to find material: {material_name}") 
            return None
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=5, enter_editmode=False, align='WORLD', 
            location=position,
            scale=(1,1,1)
        )
        childobj = bpy.context.active_object
        childobj.name = objname
        childobj.parent = obj
        childobj.data.materials.append(bpy.data.materials[material_name])
    else: childobj = childobj[0]
    return [created,childobj]

def comparelist(l1, l2):
    if not len(l1) == len(l2): return False 
    for i in range(len(l1)):
        if not l1[i] == l2[i]: return False
    return True

def getObjectFromGUID(guid: int):
    for obj in bpy.data.scenes["Scene"].collection.all_objects:
        if obj.XinTagType == "none": continue
        if obj.XinGUID.value == guid: return obj
        
def regenerateGUIDs(force = False):
    
    #special handling
    hasAbeGUID = False
    hasMunchGUID = False
        
    markers = bpy.types.Collection(bpy.data.collections.get("MARKERS")).all_objects
    print("[GUIDS] number of markers: ", len(markers))
    guids = []
    guid = 100000
    for obj in markers:
        if guid >= 9999999: break #limit, although i dont know the actual limit its propably good to have one
        if obj.XinIgnore: continue
        if obj.XinTagType in ["none", "rejectdest", "launchdest", "shadow"]: continue
        obj.XinGUID.hasGUID = False
        obj_name = obj.name.split('.')[0].split(' ')[0]
        if not guid in guids:
        #handle special cases
            match(obj.XinTagType):
                #Need to handle abe and munchs hard coded guids else crash
                case "actor":
                    if obj.XinActor.type == "mudokon" and obj.XinActor.abe:
                        if not hasAbeGUID:
                            obj.XinGUID.value = 1
                            hasAbeGUID = True
                            #guid -= 1
                        else:
                            print("[GUIDS] Duplicate Abe detected. Ignoring")
                    elif obj.XinActor.type == "munch":
                        if not hasMunchGUID:
                            obj.XinGUID.value = 2
                            hasMunchGUID = True
                            #guid -= 1
                        else:
                            print("[GUIDS] Duplicate Munch detected. Ignoring")
                    else:
                        obj.XinGUID.value = guid
                        obj.XinGUID.hasGUID = True
                        guids.append(guid)
                        print(f"[GUIDS] Setting {obj.name}'s GUID -> {obj.XinGUID.value}")
                        guid += 1
                case _: # Everything else
                    obj.XinGUID.value = guid
                    obj.XinGUID.hasGUID = True
                    guids.append(guid)
                    print(f"[GUIDS] Setting {obj.name}'s GUID -> {obj.XinGUID.value}")
                    guid += 1

        #guid += 1

def loadactor():
    
    pass

classes = (
    
    GUID,
    ActorPointer,
    ActorPointerList,
    Actor, # new master class contains all Actor Components and attributes
    Actor.LegMotion,
    Actor.FlyingMotion,
    Actor.SimpleMotion,
    Actor.Ear,
    Actor.MunchAnimation,
    Actor.MudokonAnimation,
    Actor.SimpleAnimation,
    Actor.DoorAnimation,
    Actor.TeleporterAnimation,
    Actor.SligAnimation,
    Actor.Lever360Animation,
    Actor.FootSwitchAnimation,
    Actor.FuzzleAnimation,
    Actor.VendingMachineAnimation,
    Actor.BigBroAnimation,
    Actor.NullAnimation,
    Actor.GlukkonAnimation,
    Actor.WheelchairAnimation,
    Actor.ParamiteAnimation,
    Actor.ScrabAnimation,
    Actor.GenericParticlesAnimation,
    Actor.MeepAnimation,
    Actor.InternAnimation,
    Actor.SlogAnimation,
    Actor.VykkerAnimation,
    Actor.RecyclerAnimation,
    Actor.CandyStriperAnimation,
    Actor.Behavior,
    Actor.Job,
    Actor.Doves,
    Actor.ZapFx,
    Actor.AssetLock,
    Actor.SparkleStream,
    Actor.Weapon,
    Actor.Broadcaster,
    Actor.Collectable,
    Actor.PowerUp,
    Actor.Shadow,
    Actor.LifeCycle,
    Actor.Explosion,
    Actor.Target,
    Actor.Bullseye,
    Actor.ShortGoal,
    Actor.Transformer,
    Actor.OnOffSwitch,
    Actor.AttachmentSpawner,
    Actor.Floatation,
    Actor.ActorTally,
    Actor.ActorTally2,
    Actor.ActorTally3,
    Actor.ActorTally4,
    Actor.ActorTally5,
    Actor.TextDisplay,
    Actor.TextDisplay2,
    Actor.TextDisplay3,
    Actor.TextDisplay4,
    Actor.TextDisplay5,
    Actor.TextDisplay6,
    Actor.TextDisplay7,
    Actor.TextDisplay8,
    Actor.TextDisplay9,
    Actor.TextDisplay10,
    Actor.TextDisplay11,
    Actor.TextDisplay12,
    Actor.TextDisplay13,
    ### NEXT CLASS IN CLASSES SEQUENCE
    
    Waypoint,
    Waypoint.NavPath,
    
    Camera,
    CameraTransition,
    ScriptTrigger,
    LayoutTransition,
    Ambiance,
    NavPath,

    GroundCreateOperator,
    GroundApplyOperator,
    Ground,

    ExportXinTagsOperator,
    UpdateModelsOperator,
    #RequestRandomOperator,
    ExportGeo,
    
    LoadAllAssets_BTN,
    
    AddMunchObject_Root,
    AddMunchMaker_characters,
    AddMunchMarker_interactables,
    AddMunchMarker_scriptables,
    AddMunchMarker_environment,
    AddMunchMarker_other,

    AddMunchMarker,
    Xin_Add_Marker,

    #BasicMenu,
    CreateXinScene,
    MO_Folder,
    MunchesOddysee,
    XinTagsPanel
)

def update_property(scene, depsgraph):
    for update in depsgraph.updates:
        if not isinstance(update.id, bpy.types.Object): return
        obj = update.id.original
        match obj.XinTagType:
            case "rejectdest":
                obj.parent.XinActor.rejectdest = obj.location
                break
            case "launchdest":
                obj.parent.XinActor.launchdest = obj.location
                break
                    
        
def cleanup():
    print(bpy.app.handlers.depsgraph_update_post)
    b = [v for v in bpy.app.handlers.depsgraph_update_post if "update_property" in str(v)]
    for v in b:
        print("[CLEANUP] removing", v)
        bpy.app.handlers.depsgraph_update_post.remove(v)

msgbusOwner = object()
last_active = None
def on_active_object_changed():
    global last_active, allow_update
    if allow_update == False: return
    obj = bpy.context.view_layer.objects.active
    if obj == None: 
        if last_active == None: return
        if last_active.XinActor.has_rejectdest:
            bpy.data.objects["REJECTDEST"].parent = None
            bpy.data.objects["REJECTDEST"].hide_set(True)
        if last_active.XinActor.has_launchdest:
            bpy.data.objects["LAUNCHDEST"].parent = None
            bpy.data.objects["LAUNCHDEST"].hide_set(True)
        return
    if obj.XinTagType in ["rejectdest", "launchdest"]: return
    if last_active == None: 
        if obj.XinActor.has_rejectdest:
            bpy.data.objects["REJECTDEST"].parent = obj
            bpy.data.objects["REJECTDEST"].hide_set(False)
            bpy.data.objects["REJECTDEST"].location = obj.XinActor.rejectdest
            
        else:
            bpy.data.objects["REJECTDEST"].parent = None
            bpy.data.objects["REJECTDEST"].hide_set(True)
        if obj.XinActor.has_launchdest:
            bpy.data.objects["LAUNCHDEST"].parent = obj
            bpy.data.objects["LAUNCHDEST"].hide_set(False)
            bpy.data.objects["LAUNCHDEST"].location = obj.XinActor.launchdest
        else:
            bpy.data.objects["LAUNCHDEST"].parent = None
            bpy.data.objects["LAUNCHDEST"].hide_set(True)
            
    else: 
        if obj.XinActor.has_rejectdest:
            bpy.data.objects["REJECTDEST"].parent = obj
            bpy.data.objects["REJECTDEST"].hide_set(False)
            bpy.data.objects["REJECTDEST"].location = obj.XinActor.rejectdest
        else:
            bpy.data.objects["REJECTDEST"].parent = None
            bpy.data.objects["REJECTDEST"].hide_set(True)
        if obj.XinActor.has_launchdest:
            bpy.data.objects["LAUNCHDEST"].parent = obj
            bpy.data.objects["LAUNCHDEST"].hide_set(False)
            bpy.data.objects["LAUNCHDEST"].location = obj.XinActor.launchdest
        else:
            bpy.data.objects["LAUNCHDEST"].parent = None
            bpy.data.objects["LAUNCHDEST"].hide_set(True)
    last_active = obj

def register():
    print("[[[Beginning Registeration]]]")
   
    #dir_path = os.path.dirname(bpy.data.filepath)
    
    #INFO(sys.version.split(' ')[0])
    
    #if dir_path not in sys.path:
    #    sys.path.append(dir_path)
        
    for cl in classes:
        bpy.utils.register_class(cl)
    bpy.types.VIEW3D_MT_add.append(AddMunchMarker.draw)
    bpy.app.handlers.depsgraph_update_post.append(update_property)
    #default storage
    bpy.types.Object.XinVS = {
        "launchdest" : (0.0,0.0,60.0),
        "launchdest_setting" : False,
        "rejectdest" : (0.0,0.0,30.0),
        "rejectdest_setting" : False
        } # variable storage
    
    bpy.types.Object.XinVisGeo                 = BoolProperty(name="Visual Geometry",       description="Check this to build the object into the levels visual geometry (Just what can be seen)",     default=False)
    bpy.types.Object.XinNavGeo                 = BoolProperty(name="Nav Geometry",          description="Check this to build the object into the levels navigation geometry (the things that prevent ai from walking into unwanted areas or off edges, but doesnt physicaly stop them)", default=False)
    bpy.types.Object.XinColGeo                 = BoolProperty(name="Collision Geometry",    description="Check this to build the object into the levels collision geometry (The actual physical geometry that the actors collide with)",  default=False)
    bpy.types.Object.XinIgnore                 = BoolProperty(name="Ignore Tag",            description="Use this in case you want to build the tags model into the level directly. the tag wont exist in the xin file, will not consume a guid and will only be visual/nav/col which ever you enabled.",  default=False)
        
    bpy.types.Object.XinTagType                = EnumProperty(
        name="Tag Type",
        description="The type of tag in the Layout",
        items=[
            ("none", "None", "This object is not a Xin Tag"),
            ("actor","Actor","This tag is an Actor, the most common type of tag used for all characters and interactable entities in the game"),
            ("waypoint","Waypoint","Used for various things like ladders or patrol paths, making use of navpaths within them."),
            ("camera","Camera","This tag is a Camera, Used to view the game world"),
            ("cameratransition","Camera Transition","The Camera transition controls the swaping of the active camera in the layout"),
            ("scripttrigger","Script Trigger","Runs custom scripts when an actor enters or exits it or by another means"),
            ("layouttransition","Layout Transition","Controls the level change"),
            ("ambiance","Ambiance","Usually background sounds or effects, like birds chirping, or machinary"),
            ("navpath","Nav Path","I think this is an older version of the tag used in the waypoint. It has its own position, rotation and GUID."),
            ("rejectdest","Reject Destination","This object represents the reject destination of the parent objects rejectdest attribute"),
            ("launchdest","Launch Destination","This object represents the launch destination of the parent objects launchdest attribute"),
            ("editor_ground", "Ground Tilemap", "An object to Construct Ground"),
        
        ],
        update=update_tagtype
    )
    
    bpy.types.Scene.XinMO_Folder                            = PointerProperty(type=MO_Folder)
    
    bpy.types.Scene.IsXinScene                              = BoolProperty(name="Is Xin Scene", description = "if this scene has been set up as a Xin Layout Scene for MO", default = False)

    bpy.types.Object.XinMeshController                      = MeshController()
    bpy.types.Object.XinActor                               = PointerProperty(type=Actor)
    bpy.types.Object.XinComponentLegMotion                  = PointerProperty(type=Actor.LegMotion)
    bpy.types.Object.XinComponentFlyingMotion               = PointerProperty(type=Actor.FlyingMotion)
    bpy.types.Object.XinComponentSimpleMotion               = PointerProperty(type=Actor.SimpleMotion)
    bpy.types.Object.XinComponentEar                        = PointerProperty(type=Actor.Ear)
    bpy.types.Object.XinComponentMunchAnimation             = PointerProperty(type=Actor.MunchAnimation)
    bpy.types.Object.XinComponentMudokonAnimation           = PointerProperty(type=Actor.MudokonAnimation)
    bpy.types.Object.XinComponentSimpleAnimation            = PointerProperty(type=Actor.SimpleAnimation)
    bpy.types.Object.XinComponentDoorAnimation              = PointerProperty(type=Actor.DoorAnimation)
    bpy.types.Object.XinComponentTeleporterAnimation        = PointerProperty(type=Actor.TeleporterAnimation)
    bpy.types.Object.XinComponentSligAnimation              = PointerProperty(type=Actor.SligAnimation)
    bpy.types.Object.XinComponentLever360Animation          = PointerProperty(type=Actor.Lever360Animation)
    bpy.types.Object.XinComponentFootSwitchAnimation        = PointerProperty(type=Actor.FootSwitchAnimation)
    bpy.types.Object.XinComponentFuzzleAnimation            = PointerProperty(type=Actor.FuzzleAnimation)
    bpy.types.Object.XinComponentVendingMachineAnimation    = PointerProperty(type=Actor.VendingMachineAnimation)
    bpy.types.Object.XinComponentBigBroAnimation            = PointerProperty(type=Actor.BigBroAnimation)
    bpy.types.Object.XinComponentNullAnimation              = PointerProperty(type=Actor.NullAnimation)
    bpy.types.Object.XinComponentGlukkonAnimation           = PointerProperty(type=Actor.GlukkonAnimation)
    bpy.types.Object.XinComponentWheelchairAnimation        = PointerProperty(type=Actor.WheelchairAnimation)
    bpy.types.Object.XinComponentParamiteAnimation          = PointerProperty(type=Actor.ParamiteAnimation)
    bpy.types.Object.XinComponentScrabAnimation             = PointerProperty(type=Actor.ScrabAnimation)
    bpy.types.Object.XinComponentGenericParticlesAnimation  = PointerProperty(type=Actor.GenericParticlesAnimation)
    bpy.types.Object.XinComponentMeepAnimation              = PointerProperty(type=Actor.MeepAnimation)
    bpy.types.Object.XinComponentInternAnimation            = PointerProperty(type=Actor.InternAnimation)
    bpy.types.Object.XinComponentSlogAnimation              = PointerProperty(type=Actor.SlogAnimation)
    bpy.types.Object.XinComponentVykkerAnimation            = PointerProperty(type=Actor.VykkerAnimation)
    bpy.types.Object.XinComponentRecyclerAnimation          = PointerProperty(type=Actor.RecyclerAnimation)
    bpy.types.Object.XinComponentCandyStriperAnimation      = PointerProperty(type=Actor.CandyStriperAnimation)
    bpy.types.Object.XinComponentBehavior                   = PointerProperty(type=Actor.Behavior)
    bpy.types.Object.XinComponentJob                        = PointerProperty(type=Actor.Job)
    bpy.types.Object.XinComponentDoves                      = PointerProperty(type=Actor.Doves)
    bpy.types.Object.XinComponentZapFx                      = PointerProperty(type=Actor.ZapFx)
    bpy.types.Object.XinComponentAssetLock                  = PointerProperty(type=Actor.AssetLock)
    bpy.types.Object.XinComponentSparkleStream              = PointerProperty(type=Actor.SparkleStream)
    bpy.types.Object.XinComponentWeapon                     = PointerProperty(type=Actor.Weapon)
    bpy.types.Object.XinComponentBroadcaster                = PointerProperty(type=Actor.Broadcaster)
    bpy.types.Object.XinComponentCollectable                = PointerProperty(type=Actor.Collectable)
    bpy.types.Object.XinComponentPowerUp                    = PointerProperty(type=Actor.PowerUp)
    bpy.types.Object.XinComponentShadow                     = PointerProperty(type=Actor.Shadow)
    bpy.types.Object.XinComponentLifeCycle                  = PointerProperty(type=Actor.LifeCycle)
    bpy.types.Object.XinComponentExplosion                  = PointerProperty(type=Actor.Explosion)
    bpy.types.Object.XinComponentTarget                     = PointerProperty(type=Actor.Target)
    bpy.types.Object.XinComponentBullseye                   = PointerProperty(type=Actor.Bullseye)
    bpy.types.Object.XinComponentShortGoal                  = PointerProperty(type=Actor.ShortGoal)
    bpy.types.Object.XinComponentTransformer                = PointerProperty(type=Actor.Transformer)
    bpy.types.Object.XinComponentOnOffSwitch                = PointerProperty(type=Actor.OnOffSwitch)
    bpy.types.Object.XinComponentAttachmentSpawner          = PointerProperty(type=Actor.AttachmentSpawner)
    bpy.types.Object.XinComponentFloatation                 = PointerProperty(type=Actor.Floatation)
    bpy.types.Object.XinComponentActorTally                 = PointerProperty(type=Actor.ActorTally)
    bpy.types.Object.XinComponentActorTally2                = PointerProperty(type=Actor.ActorTally2)
    bpy.types.Object.XinComponentActorTally3                = PointerProperty(type=Actor.ActorTally3)
    bpy.types.Object.XinComponentActorTally4                = PointerProperty(type=Actor.ActorTally4)
    bpy.types.Object.XinComponentActorTally5                = PointerProperty(type=Actor.ActorTally5)
    bpy.types.Object.XinComponentTextDisplay                = PointerProperty(type=Actor.TextDisplay)
    bpy.types.Object.XinComponentTextDisplay2               = PointerProperty(type=Actor.TextDisplay2)
    bpy.types.Object.XinComponentTextDisplay3               = PointerProperty(type=Actor.TextDisplay3)
    bpy.types.Object.XinComponentTextDisplay4               = PointerProperty(type=Actor.TextDisplay4)
    bpy.types.Object.XinComponentTextDisplay5               = PointerProperty(type=Actor.TextDisplay5)
    bpy.types.Object.XinComponentTextDisplay6               = PointerProperty(type=Actor.TextDisplay6)
    bpy.types.Object.XinComponentTextDisplay7               = PointerProperty(type=Actor.TextDisplay7)
    bpy.types.Object.XinComponentTextDisplay8               = PointerProperty(type=Actor.TextDisplay8)
    bpy.types.Object.XinComponentTextDisplay9               = PointerProperty(type=Actor.TextDisplay9)
    bpy.types.Object.XinComponentTextDisplay10              = PointerProperty(type=Actor.TextDisplay10)
    bpy.types.Object.XinComponentTextDisplay11              = PointerProperty(type=Actor.TextDisplay11)
    bpy.types.Object.XinComponentTextDisplay12              = PointerProperty(type=Actor.TextDisplay12)
    bpy.types.Object.XinComponentTextDisplay13              = PointerProperty(type=Actor.TextDisplay13)
    ### NEXT OBJECT EXTENTION IN REGESTER FUNCTION
    
    bpy.types.Object.XinWaypoint                            = PointerProperty(type=Waypoint)
    
    bpy.types.Object.XinWaypointNavPaths                    = CollectionProperty(type=Waypoint.NavPath)
    
    bpy.types.Object.XinCamera                              = PointerProperty(type=Camera)
    
    bpy.types.Object.XinCameraTransition                    = PointerProperty(type=CameraTransition)
    
    bpy.types.Object.XinScriptTrigger                       = PointerProperty(type=ScriptTrigger)
    
    bpy.types.Object.XinLayoutTransition                    = PointerProperty(type=LayoutTransition)
    
    bpy.types.Object.XinAmbiance                            = PointerProperty(type=Ambiance)
    
    bpy.types.Object.XinNavPath                             = PointerProperty(type=NavPath)
    
    bpy.types.Object.EditorGround                           = PointerProperty(type=Ground)
    
    bpy.types.Object.XinGUID                                = PointerProperty(type=GUID)

    
    bpy.app.timers.register(value_modify_timer)
    
    bpy.msgbus.subscribe_rna(
        key=(bpy.types.LayerObjects, "active"),
        owner=msgbusOwner,
        args=(),
        notify=on_active_object_changed
    )

def unregister():
    global addonpath
    print("[[[Beginning Unregisteration]]]")
    
    bpy.msgbus.clear_by_owner(msgbusOwner)
    
    if bpy.app.timers.is_registered(value_modify_timer):
        bpy.app.timers.unregister(value_modify_timer)
    bpy.types.VIEW3D_MT_add.remove(AddMunchMarker.draw)
    #bpy.app.handlers.depsgraph_update_post.remove(update_property)
    
    bpy.types.Object.XinVS = None
    
    del bpy.types.Object.XinGUID    
    
    del bpy.types.Scene.XinMO_Folder
    
    del bpy.types.Object.XinMeshController
    del bpy.types.Object.XinActor
    del bpy.types.Object.XinComponentLegMotion
    del bpy.types.Object.XinComponentFlyingMotion
    del bpy.types.Object.XinComponentSimpleMotion
    del bpy.types.Object.XinComponentEar
    del bpy.types.Object.XinComponentMunchAnimation
    del bpy.types.Object.XinComponentMudokonAnimation
    del bpy.types.Object.XinComponentSimpleAnimation
    del bpy.types.Object.XinComponentDoorAnimation
    del bpy.types.Object.XinComponentTeleporterAnimation
    del bpy.types.Object.XinComponentSligAnimation
    del bpy.types.Object.XinComponentLever360Animation
    del bpy.types.Object.XinComponentFootSwitchAnimation
    del bpy.types.Object.XinComponentFuzzleAnimation
    del bpy.types.Object.XinComponentVendingMachineAnimation
    del bpy.types.Object.XinComponentBigBroAnimation
    del bpy.types.Object.XinComponentNullAnimation
    del bpy.types.Object.XinComponentGlukkonAnimation
    del bpy.types.Object.XinComponentWheelchairAnimation
    del bpy.types.Object.XinComponentParamiteAnimation
    del bpy.types.Object.XinComponentScrabAnimation
    del bpy.types.Object.XinComponentGenericParticlesAnimation
    del bpy.types.Object.XinComponentMeepAnimation
    del bpy.types.Object.XinComponentInternAnimation
    del bpy.types.Object.XinComponentSlogAnimation
    del bpy.types.Object.XinComponentVykkerAnimation
    del bpy.types.Object.XinComponentRecyclerAnimation
    del bpy.types.Object.XinComponentCandyStriperAnimation
    del bpy.types.Object.XinComponentBehavior
    del bpy.types.Object.XinComponentJob
    del bpy.types.Object.XinComponentDoves
    del bpy.types.Object.XinComponentZapFx
    del bpy.types.Object.XinComponentAssetLock
    del bpy.types.Object.XinComponentSparkleStream
    del bpy.types.Object.XinComponentWeapon
    del bpy.types.Object.XinComponentBroadcaster
    del bpy.types.Object.XinComponentCollectable
    del bpy.types.Object.XinComponentPowerUp
    del bpy.types.Object.XinComponentShadow
    del bpy.types.Object.XinComponentLifeCycle
    del bpy.types.Object.XinComponentExplosion
    del bpy.types.Object.XinComponentTarget
    del bpy.types.Object.XinComponentBullseye
    del bpy.types.Object.XinComponentShortGoal
    del bpy.types.Object.XinComponentTransformer
    del bpy.types.Object.XinComponentOnOffSwitch
    del bpy.types.Object.XinComponentAttachmentSpawner
    del bpy.types.Object.XinComponentFloatation
    del bpy.types.Object.XinComponentActorTally
    del bpy.types.Object.XinComponentActorTally2
    del bpy.types.Object.XinComponentActorTally3
    del bpy.types.Object.XinComponentActorTally4
    del bpy.types.Object.XinComponentActorTally5
    del bpy.types.Object.XinComponentTextDisplay
    del bpy.types.Object.XinComponentTextDisplay2
    del bpy.types.Object.XinComponentTextDisplay3
    del bpy.types.Object.XinComponentTextDisplay4
    del bpy.types.Object.XinComponentTextDisplay5
    del bpy.types.Object.XinComponentTextDisplay6
    del bpy.types.Object.XinComponentTextDisplay7
    del bpy.types.Object.XinComponentTextDisplay8
    del bpy.types.Object.XinComponentTextDisplay9
    del bpy.types.Object.XinComponentTextDisplay10
    del bpy.types.Object.XinComponentTextDisplay11
    del bpy.types.Object.XinComponentTextDisplay12
    del bpy.types.Object.XinComponentTextDisplay13   
    
    del bpy.types.Object.XinWaypoint
    del bpy.types.Object.XinWaypointNavPaths
    
    del bpy.types.Object.XinCamera
    
    del bpy.types.Object.XinCameraTransition
    
    del bpy.types.Object.XinScriptTrigger
    
    del bpy.types.Object.XinLayoutTransition
    
    del bpy.types.Object.XinAmbiance
    
    del bpy.types.Object.XinNavPath
    
    del bpy.types.Object.EditorGround
    
    cleanup()
    
    for cl in reversed(classes):
        print("Unregistering class:", cl)
        bpy.utils.unregister_class(cl)
    

vmt_table = {
    #[
    #    get_func,
    #    mod_func,
    #    target,
    #    direction,
    #    object
    #]
}
# run the modify func
# run the get
# test the get agains the target value
# if the value is met or exceded it wont do anything
# See in Actor class update_state

#user must set the above values then 
def value_modify_timer():
    global vmt_table
    for i in range(len(vmt_table.values())):
        action = list(vmt_table.values())[i]
        #print(action[4])
        if action[3] < 0:
            if action[1](action[4]) > action[2]:
                action[0](action[4])
        elif action[3] > 0:
            if action[1](action[4]) < action[2]:
                action[0](action[4])
    return 0.01

haslogged = False
def LOG(obj, overwrite = True):
    global haslogged
    f = None

    f = open("./log.txt", f"{'a' if haslogged is True or overwrite is False else'w'}")
    f.write(str(obj)+"\n")
    f.close()
    haslogged = True


if __name__ == "__main__":
    
    register()
