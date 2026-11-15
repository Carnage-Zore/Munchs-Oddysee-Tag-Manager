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

import os, mathutils, math, random, struct, operator, glob, array, json
import numpy as np

#import tkinter as tk
#from tkinter import filedialog
"""
MY LIST
 The standard list reverse method is dumb.
 it is dumb as it mutates instead of returning. doing this is fine for complex objects but not a primitive list
 additionaly the buit-in reversed() func doesnt return the type list that was input an has to be cast to the type after
 They shoulda just added the reversed func to the list type as a seperate method that returns instead of mutating
 the hacky and unreadable solution is value = [1, 2, 3][::-1] while small its not intuitive
 and could be replaced with 'value = [1, 2, 3].reversed()'
 In Summary:
 'value = [1, 2, 3].reversed()' -> readable, intuitive, allows the reverse() method to still exist if you wanted to mutate
 instead of:
 'value = [1, 2, 3].reverse()' -> mutates instead of returning, unintuitive
 'value = list(reversed([1, 2, 3]))' -> doesnt return the list type that was input, needs to be cast, unintuitive
 'value = [1, 2, 3][::-1]' -> hacky, unintuitive, unreadable
 so i made a class to implement it :)
"""
class mylist(list):
    def reversed(self):
        return mylist(self[::-1])

def wf(file, data, Bytes):
    writemode = "w" if not Bytes else "wb"
    with open(file, writemode) as f:
        f.write(data)
    
def angle_from_matrix(matrix):
    sy = np.sqrt(matrix[0,0] * matrix[0,0] + matrix[1,0] * matrix[1,0])
    singular = sy < 1e-6
    X = None
    Y = None
    Z = None
    if not singular:
        X = float(np.arctan2(matrix[2,1], matrix[2,2])) 
        Y = float(np.arctan2(-matrix[2,0], sy))
        Z = float(np.arctan2(matrix[1,0], matrix[0,0]))
    else:
        X = float(np.arctan2(matrix[1,2], matrix[1,1]))
        Y = float(np.arctan2(-matrix[2,0], sy))
        Z = 0.0
    return [round(math.degrees(X),2), round(math.degrees(Y),2), round(math.degrees(Z),2)]

def matrix_rotate(matrix, vertex):
    res = np.dot(matrix, vertex)
    return [float(res[0]),float(res[1]),float(res[2])]

def pack_number(dest, src, pos, frm):
    packed = struct.pack(frm, src)
    for i in range(len(list(packed))):
        dest[pos+i] = packed[i]

def operate(val1, val2, operation:str):
    op = operator
    ops = {
        '>' : op.gt,
        '<' : op.lt,
        '>=' : op.ge,
        '<=' : op.le,
        '==' : op.eq,
        '+' : op.add,
        '-' : op.sub,
        '/' : op.truediv,
        '>>' : op.rshift,
        '<<' : op.lshift,
        '*' : op.mul
    }
    return ops[operation](val1, val2)

def ArrMath(arr1, arr2, operation:str):
    if not len(arr1) == len(arr2): return None
    res = []
    for i in range(len(arr1)):
        res.append(operate(arr1[i], arr2[i], operation))
    return res
    #return arr1

def validateVersion(parser, since=None, until=None):
    return NetImmerseFileParser.validateVersion(parser.data.header.Version, since, until)
#this parser does not acknowledge BS blocks as they are an extension of the format and not part of the base format
# Idealy in the nif.xml they would be seperated into there own section or as part of a different file completly
class NifTypes:
    class sInt:
        def __init__(self, parser, value:int=None):
            self.p = parser
            if value==None:
                self.value = struct.unpack('<i', self.p.file.read(4))[0]
        def save(self):
            self.p.file.write(struct.pack('<i', self.value))
        def set(self, value:int):
            self.value = (value + 0x80000000) % 0x100000000 - 0x80000000 # limit to 4 bytes
    class uInt:
        def __init__(self, parser, value:int=None):
            self.p = parser
            if value == None:
                self.value = struct.unpack('<I', self.p.file.read(4))[0]
        def save(self):
            self.p.file.write(struct.pack('<I', self.value))
        def set(self, value:int):
            self.value = value % 0x100000000 # limit to 4 bytes
    class uShort:
        def __init__(self, parser, value:int=None):
            self.p = parser
            if value==None:
                self.value = struct.unpack('<H', self.p.file.read(2))[0]
        def save(self):
            self.p.file.write(struct.pack('<H', self.value))
        def set(self, value:int):
            self.value = value % 0x10000 # limit to 2 bytes
    class sShort:
        def __init__(self, parser, value:int=None):
            self.p = parser
            if value==None:
                self.value = struct.unpack('<h', self.p.file.read(2))[0]
        def save(self):
            self.p.file.write(struct.pack('<h', self.value))
        def set(self, value:int):
            self.value = (value + 0x8000) % 0x10000 - 0x8000 # limit to 2 bytes
    class uByte:
        def __init__(self, parser, value:int = None):
            self.p = parser
            if value == None:
                self.value = struct.unpack('<B', self.p.file.read(1))[0]
            self.set(value)
        def save(self):
            self.p.file.write(struct.pack('<B', self.value))
        def set(self, value:int):
            self.value = value % 0x100 # limit to 1 byte
    class sByte:
        def __init__(self, parser, value:int=None):
            self.p = parser
            if value == None:
                self.value = struct.unpack('<b', self.p.file.read(1))[0]
                return
            self.set(value)
        def save(self):
            self.p.file.write(struct.pack('<b', self.value))
        def set(self, value:int):
            self.value = (value + 0x80) % 0x100 - 0x80 # limit to 1 byte
    class Char:
        def __init__(self, parser, value:str=None):
            self.p = parser
            if value==None:
                self.value = self.p.file.read(1)
                return
            self.set(value)
        def save(self):
            self.p.file.write(self.value)
        def set(self, value:str):
            self.value = bytes(value[0], "utf-8")
    class Bool:
        def __init__(self, parser, value:bool=None):
            self.p = parser
            if value == None:
                if verifyVersion(p, until=[4,0,0,2]):
                    self.internal = parser.uInt(parser)
                    self.value = self.internal.value > 0
                if verifyVersion(p, since=[4,1,0,1]):
                    self.internal = parser.uByte(parser)
                    self.value = self.internal.value > 0
                return
            self.set(value)
        def save(self):
            if verifyVersion(self.p, until=[4,0,0,2]):
                self.internal.save()
            if verifyVersion(self.p, since=[4,1,0,1]):
                self.internal.save()
        def set(self, value:bool):
            if verifyVersion(self.p, until=[4,0,0,2]):
                self.internal = self.p.uInt(p, 0x7FFFFFFF) if value==True else 0
                self.value = value
            if verifyVersion(self.p, since=[4,1,0,1]):
                self.internal = self.p.uInt(p, 0x7FFF) if value==True else 0
                self.value = value
    class Single:
        def __init__(self, parser, value:float=None):
            self.p = parser
            if value == None:
                self.value = struct.unpack('<f', self.p.file.read(1))[0]
                return
            self.set(value)
        def save(self):
            self.p.file.write(struct.pack('<f', self.value))
        def set(self, value:float):
            self.value = np.float32(value)
    class Double:
        def __init__(self, parser, value:float=None):
            self.p = parser
            if value == None:
                self.value = struct.unpack('<d', self.p.file.read(1))[0]
                return
            self.set(value)
        def save(self):
            self.p.file.write(struct.pack('<d', self.value))
        def set(self, value:float):
            self.value = value
    class SizedString:
        def __init__(self, parser, value:str = None):
            self.p = parser
            if value==None:
                self.size = self.p.u32Alt()
                self.bytes = self.p.char(self.size.value)
                return
            self.set(value)
        def save(self):
            self.size.save()
            for value in self.bytes: value.save()
        def set(self, value:str):
            self.size = NifTypes.uInt(self.p, len(value))
            self.bytes = [NifTypes.Char(self.p, c) for c in value]
    class ExtraDataString:
        def __init__(self, parser, value:str = None):
            self.p = parser
            if value==None:
                self.size = self.p.u32Alt()
                if self.size.value > 0:
                    self.string = self.p.stringAlt()
                return
            self.set(value)
        def save(self):
            self.size.save()
            if self.size.value > 0:
                self.string.save()
        def set(self, value:str):
            sizeInner = len(value)
            if sizeInner > 0:
                self.size = NifTypes.uInt(self.p, sizeInner+4)
                self.string = NifTypes.SizedString(self.p, value)
            else:
                self.size=NifTypes.uInt(self.p, 0)
                self.string = None
    class SizedBytes:
        def __init__(self, parser, value:list[int] = None):
            self.p = parser
            if value==None:
                self.size = self.p.u32Alt()
                self.bytes = self.p.u8Alt(self.size.value)
        def save(self):
            self.size.save()
            for i in range(self.size.value): self.bytes[i].save()
        def set(self, value:list[int]):
            self.size = self.p.uInt(self.p, len(value))
            self.bytes = [self.p.uByte(self.p, value[i]) for i in range(self.size.value)]
    class Vector2:
        def __init__(self, parser, value:tuple[float,float] = None):
            self.p = parser
            if value == None:
                self.x = self.p.singleAlt()
                self.y = self.p.singleAlt()
                return
            self.set(value)
        def save(self):
            self.x.save()
            self.y.save()
        def set(self, value:tuple[float,float]):
            self.x = NifTypes.Single(self.p, value[0])
            self.y = NifTypes.Single(self.p, value[1])
    class Vector3:
        def __init__(self, parser, value:tuple[float,float,float] = None):
            self.p = parser
            if value == None:
                self.x = self.p.singleAlt()
                self.y = self.p.singleAlt()
                self.z = self.p.singleAlt()
                return
            self.set(value)
        def save(self):
            self.x.save()
            self.y.save()
            self.z.save()
        def set(self, value:tuple[float,float,float]):
            self.x = NifTypes.Single(self.p, value[0])
            self.y = NifTypes.Single(self.p, value[1])
            self.z = NifTypes.Single(self.p, value[2])
    class Vector4:
        def __init__(self, parser, value:tuple[float,float,float,float] = None):
            self.p = parser
            if value == None:
                self.x = self.p.singleAlt()
                self.y = self.p.singleAlt()
                self.z = self.p.singleAlt()
                self.w = self.p.singleAlt()
                return
            self.set(value)
        def save(self):
            self.x.save()
            self.y.save()
            self.z.save()
            self.w.save()
        def set(self, value:tuple[float,float,float,float]):
            self.x = NifTypes.Single(self.p, value[0])
            self.y = NifTypes.Single(self.p, value[1])
            self.z = NifTypes.Single(self.p, value[2])
            self.w = NifTypes.Single(self.p, value[3])
    class u16Vector2:
        def __init__(self, parser, value:tuple[int,int] = None):
            self.p = parser
            if value == None:
                self.x = self.p.u16Alt()
                self.y = self.p.u16Alt()
                return
            self.set(value)
        def save(self):
            self.x.save()
            self.y.save()
        def set(self, value:tuple[int,int]):
            self.x = NifTypes.uShort(self.p, value[0])
            self.y = NifTypes.uShort(self.p, value[1])
    class u16Vector3:
        def __init__(self, parser, value:tuple[int,int,int] = None):
            self.p = parser
            if value == None:
                self.x = self.p.u16Alt()
                self.y = self.p.u16Alt()
                self.z = self.p.u16Alt()
                return
            self.set(value)
        def save(self):
            self.x.save()
            self.y.save()
            self.z.save()
        def set(self, value:tuple[int,int,int]):
            self.x = NifTypes.uShort(self.p, value[0])
            self.y = NifTypes.uShort(self.p, value[1])
            self.z = NifTypes.uShort(self.p, value[2])
    class u16Vector4:
        def __init__(self, parser, value:tuple[int,int,int,int] = None):
            self.p = parser
            if value == None:
                self.x = self.p.u16Alt()
                self.y = self.p.u16Alt()
                self.z = self.p.u16Alt()
                self.w = self.p.u16Alt()
                return
            self.set(value)
        def save(self):
            self.x.save()
            self.y.save()
            self.z.save()
            self.w.save()
        def set(self, value:tuple[int,int,int,int]):
            self.x = NifTypes.uShort(self.p, value[0])
            self.y = NifTypes.uShort(self.p, value[1])
            self.z = NifTypes.uShort(self.p, value[2])
            self.w = NifTypes.uShort(self.p, value[3]) 
    class u8Vector4:
        def __init__(self, parser, value:tuple[int,int,int,int] = None):
            self.p = parser
            if value == None:
                self.x = self.p.u8Alt()
                self.y = self.p.u8Alt()
                self.z = self.p.u8Alt()
                self.w = self.p.u8Alt()
                return
            self.set(value)
        def save(self):
            self.x.save()
            self.y.save()
            self.z.save()
            self.w.save()
        def set(self, value:tuple[int,int,int,int]):
            self.x = NifTypes.uByte(self.p, value[0])
            self.y = NifTypes.uByte(self.p, value[1])
            self.z = NifTypes.uByte(self.p, value[2])
            self.w = NifTypes.uByte(self.p, value[3])
    class Matrix33:
        def __init__(self, parser, value:tuple[tuple[float,float,float],tuple[float,float,float],tuple[float,float,float]] = None):
            self.p = parser
            if value == None:
                self.x = self.p.vec3Alt()
                self.y = self.p.vec3Alt()
                self.z = self.p.vec3Alt()
                return
            self.set(value)
        def save(self):
            self.x.save()
            self.y.save()
            self.z.save()
        def set(self, value:tuple[tuple[float,float,float],tuple[float,float,float],tuple[float,float,float]]):
            self.x = NifTypes.Vector3(self.p, value[0])
            self.y = NifTypes.Vector3(self.p, value[1])
            self.z = NifTypes.Vector3(self.p, value[2])
    class Matrix22:
        def __init__(self, parser, value:tuple[tuple[float,float],tuple[float,float]] = None):
            self.p = parser
            if value == None:
                self.x = self.p.vec3Alt()
                self.y = self.p.vec3Alt()
                return
            self.set(value)
        def save(self):
            self.x.save()
            self.y.save()
        def set(self, value:tuple[tuple[float,float],tuple[float,float]]):
            self.x = NifTypes.Vector3(self.p, value[0])
            self.y = NifTypes.Vector3(self.p, value[1])
    
    # Nif File Meta Blocks
    class Header:
        def __init__(self, parser, value:tuple[str,list[int],int]=None):
            self.p = parser
            if value == None:
                buffer = b''
                b = self.p.file.read(1)
                while not b == b'\n':
                    buffer += b
                    b = self.p.file.read(1)
                self.Header = buffer
                self.Version = mylist(self.p.s8Alt(4)).reversed()
                self.Num_Blocks = self.p.u32Alt()
        def save(self):
            self.p.file.write(self.Header + b"\n")
            for v in self.Version.reversed(): v.save()
            self.Num_Blocks.save()
        def set(self, value:tuple[str,list[int],int]):
            self.Header = bytes(value[0], "utf-8")
            self.Version = [NifTypes.sByte(self.p, v) for v in value[1]]
            self.Num_Blocks = NifTypes.uInt(self.p, value[2])
    class Footer:
        def __init__(self, parser, value:list[int] = None):
            self.p = parser
            if value == None:
                self.Num_Roots = self.p.u32Alt()
                self.Roots = self.p.s32Alt(self.Num_Roots.value)
                return
            self.set(value)
        def save(self):
            self.Num_Roots.save()
            for i in range(self.Num_Roots.value):
                self.Roots[i].save()
        def set(value:list[int]):
            self.Num_Roots = NifTypes.uInt(self.p, len(value))
            self.Roots = [NifTypes.sInt(self.p, value[i]) for i in range(self.Num_Roots.value)]
    
    # NiBlock Component parts
    class NiBoundAABB:
        def __init__(self, parser, value:tuple["NifTypes.uInt", "NifTypes.Vector3"]=None):
            self.p = parser
            if value==None:
                self.Num_Corners = self.p.u16Alt()
                self.Corners = self.p.vec3Alt()
                return
            self.set(value)
        def save(self):
            self.Num_Corners.save()
            self.Corners.save()
        def set(self, value:tuple["NifTypes.uInt", "NifTypes.Vector3"]):
            self.Num_Corners = value[0]
            self.Corners = value[1]
    class NiBound:
        def __init__(self, parser, value:tuple["NifTypes.Vector3", "NifTypes.Single", "NifTypes.NiBoundAABB"]=None):
            self.p = parser
            if value == None:
                self.Center = self.p.vec3Alt()
                self.Radius = self.p.single()
                if validateVersion(self.p, [20,3,0,9], [20,3,0,9]): 
                    self.DIV2_AABB = NifTypes.NiBoundAABB(self.p)
                return
            self.set(value)
        def save(self):
            self.Center.save()
            parser.single()
            if validateVersion(self.p, [20,3,0,9], [20,3,0,9]): 
                self.DIV2_AABB.save()
        def set(value:tuple["NifTypes.Vector3", "NifTypes.Single", "NifTypes.NiBoundAABB"]):
            self.Center = value[0]
            self.Radius = value[1]
            if value[2] != None:
                self.DIV2_AABB = value[2]
    class BoxBV:
        def __init__(self, parser, value:tuple["NifTypes.Vector3",tuple["NifTypes.Vector3","NifTypes.Vector3","NifTypes.Vector3"],"NifTypes.Vector3"]=None):
            self.p = parser
            if value==None:
                self.Center = self.p.vec3Alt()
                self.Axis = self.p.vec3Alt(3)
                self.Extent = self.p.vec3Alt()
                return
            self.set(value)
        def save(self):
            self.Center.save()
            [self.Axis[i].save() for i in range(3)]
            self.Extent.save()
        def set(self, value:tuple["NifTypes.Vector3",tuple["NifTypes.Vector3","NifTypes.Vector3","NifTypes.Vector3"],"NifTypes.Vector3"]):
            self.Center = value[0]
            self.Axis = [i for i in value[1][i]]
            self.Extent = value[2]
    class CapsuleBV:
        def __init__(self, parser, value:tuple["NifTypes.Vector3","NifTypes.Vector3", "NifTypes.Single", "NifTypes.Single"]=None):
            self.p = parser
            if value == None:
                self.Center = self.p.vec3Alt()
                self.Origin = self.p.vec3Alt()
                self.Extent = self.p.singleAlt()
                self.Radius = self.p.singleAlt()
                return
            self.set(value)
        def save(self):
            self.Center.save()
            self.Origin.save()
            self.Extent.save()
            self.Radius.save()
        def set(self, value:tuple["NifTypes.Vector3","NifTypes.Vector3", "NifTypes.Single", "NifTypes.Single"]):
            self.Center = value[0]
            self.Origin = value[1]
            self.Extent = value[2]
            self.Radius = value[3]
    class NiPlane:
        def __init__(self, parser, value:tuple["NifTypes.Vector3", "NifTypes.Single"]=None):
            self.p = parser
            if value == None:
                self.Normal = parser.vec3Alt()
                self.Constant = parser.single()
                return
            self.set(value)
        def save(self):
            self.Normal.save()
            self.Constant.save()
        def set(self, value:tuple["NifTypes.Vector3", "NifTypes.Single"]):
            self.Normal = value[0]
            self.Constant = value[1]
    class HalfSpaceBV:
        def __init__(self, parser, value:tuple["NifTypes.NiPlane", "NifTypes.Vector3"]=None):
            if value == None:
                self.Plane = parser.NiPlane(parser)
                self.Center = parser.vec3Alt()
                return
            self.set(value)
        def save(self):
            self.Plane.save()
            self.Center.save()
        def set(self, value:tuple["NifTypes.NiPlane", "NifTypes.Vector3"]):
            self.Plane = value[0]
            self.Center = value[1]
    class BoundingVolume:
        def __init__(self, parser, value:tuple["NifTypes.sInt", "NifTypes.NiBound | NifTypes.BoxBV | NifTypes.CapsuleBV | NifTypes.HalfSpaceBV | None"]=None):
            self.p = parser
            if value==None:
                self.Collision_Type = self.p.s32Alt()
                match(self.Collision_Type.value):
                    case 0: self.Sphere = NifTypes.NiBound(self.p)
                    case 1: self.Box = NifTypes.BoxBV(self.p)
                    case 2: self.Capsule = NifTypes.CapsuleBV(self.p)
                    case 5: self.Half_Space = NifTypes.HalfSpaceBV(self.p)
                return
            self.set(value)
        def save(self):
            self.Collision_Type.save()
            match(self.Collision_Type.value):
                case 0: self.Sphere.save()
                case 1: self.Box.save()
                case 2: self.Capsule.save()
                case 5: self.half_Space.save()
        def set(self, value:tuple["NifTypes.sInt", "NifTypes.NiBound | NifTypes.BoxBV | NifTypes.CapsuleBV | NifTypes.HalfSpaceBV | None"]):
            self.Collision_Type = value[0]
            match(self.Collision_Type.value):
                case 0: self.Sphere = value[1]
                case 1: self.Box = value[1]
                case 2: self.Capsule = value[1]
                case 5: self.half_Space = value[1]
    class LegacyExtraData:
        def __init__(self, parser, value:tuple["NifTypes.Bool", "NifTypes.SizedString | None", "NifTypes.uInt | None", "NifTypes.SizedString | None", "NifTypes.uByte"]=None):
            self.p = parser
            if value == None:
                self.Has_Extra_Data = self.p.boolAlt()
                if self.Has_Extra_Data.value:
                    self.Extra_Prop_Name = self.p.stringAlt()
                    self.Extra_Ref_ID = self.p.u32Alt()
                    self.Extra_String = self.p.stingAlt()
                self.Unknown_Byte_1 = self.p.u8Alt()
                return
            self.set(value)
        def save(self):
            self.Has_Extra_Data.save() 
            if self.Has_Extra_Data.value:
                self.Extra_Prop_Name.save()
                self.Extra_Ref_ID.save()
                self.Extra_String.save()
            self.Unknown_Byte_1.save()
        def set(self, value:tuple["NifTypes.Bool", "NifTypes.SizedString | None", "NifTypes.uInt | None", "NifTypes.SizedString | None", "NifTypes.uByte"]):
            self.Has_Extra_Data = value[0]
            if self.Has_Extra_Data.value:
                self.Extra_Prop_Name = value[1]
                self.Extra_Ref_ID = value[2]
                self.Extra_String = value[3]
            self.Unknown_Byte_1 = value[4]
    class ByteArray:
        def __init__(self, parser, value:tuple["NifTypes.uInt", list["NifTypes.uByte"]]=None):
            self.p = parser
            if value == None:
                self.Data_Size = self.p.u32()
                self.Data = self.p.u8(self.Data_Size.value)
                return
            self.set(value)
        def save(self):
            self.Data_Size.save()
            for i in range(self.Data_Size.value): self.Data[i].Save()
        def set(self, value:tuple["NifTypes.uInt", list["NifTypes.uByte"]]):
            self.Data_Size = value[0]
            self.Data = value[1]
            
    # NiBlock Components
    class NiObjectNET:
        def __init__(self, parser, value:tuple[
                    "NifTypes.SizedString", 
                    "NifTypes.LegacyExtraData | None", 
                    "NifTypes.sInt | None", 
                    "NifTypes.uInt | None", 
                    list["NifTypes.sInt"]|None, 
                    "NifTypes.sInt | None"
                ]=None):
            self.p = parser
            if value == None:
                self.Name = self.p.stringAlt()
                if validateVersion(self.p, until=[2,3]):
                    self.Legacy_Extra_Data = NifTypes.LegacyExtraData(self.p)
                if validateVersion(self.p, since=[3], until=[4,2,2]):
                    self.Extra_Data = self.p.s32()
                if validateVersion(self.p, since=[10,0,1]):
                    self.Num_Extra_Data_List = self.p.u32()
                    self.Extra_Data_List = self.p.s32(self.Num_Extra_Data_List.value)
                if validateVersion(self.p, since=[3]):
                    self.Controller = self.p.s32()
                return
            self.set(value)
        def save(self):
            self.Name.save()
            if validateVersion(self.p, until=[2,3]):
                self.Legacy_Extra_Data.save()
            if validateVersion(self.p, since=[3], until=[4,2,2]):
                self.Extra_Data.save()
            if validateVersion(self.p, since=[10,0,1]):
                self.Num_Extra_Data_List.save()
                for i in range(self.Num_Extra_Data_List.value): self.Extra_Data_List[i].save()
            if validateVersion(self.p, since=[3]):
                self.Controller.save()
        def set(self, value:tuple[
                    "NifTypes.SizedString", 
                    "NifTypes.LegacyExtraData | None", 
                    "NifTypes.sInt | None", 
                    "NifTypes.uInt | None", 
                    list["NifTypes.sInt"]|None, 
                    "NifTypes.sInt | None"
                ]):
            self.Name = value[0]
            if validateVersion(self.p, until=[2,3]):
                self.Legacy_Extra_Data = value[1]
            if validateVersion(self.p, since=[3], until=[4,2,2]):
                self.Extra_Data = value[2]
            if validateVersion(self.p, since=[10,0,1]):
                self.Num_Extra_Data_List = value[3]
                self.Extra_Data_List = value[4]
            if validateVersion(self.p, since=[3]):
                self.Controller = value[5]
        def assign(self, other:"NifTypes.NiObjectNET"):
            self.Name = other.Name
            if validateVersion(self.p, until=[2,3]):
                self.Legacy_Extra_Data = other.Legacy_Extra_Data
            if validateVersion(self.p, since=[3], until=[4,2,2]):
                self.Extra_Data = other.Extra_Data
            if validateVersion(self.p, since=[10,0,1]):
                self.Num_Extra_Data_List = other.Num_Extra_Data_List
                self.Extra_Data_List = other.Extra_Data_List
            if validateVersion(self.p, since=[3]):
                self.Controller = other.Controller
    class NiAVObject(NiObjectNET):
        def __init__(self, parser, value:tuple[
                    "NifTypes.NiObjectNET",
                    "NifTypes.uShort | None", 
                    "NifTypes.Vector3", 
                    "NifTypes.Matrix33", 
                    "NifTypes.Single", 
                    "NifTypes.Vector3 | None", 
                    "NifTypes.uInt", 
                    list["NifTypes.sInt"], 
                    "NifTypes.uInt | None", 
                    "NifTypes.uByte | None", 
                    "NifTypes.Bool", 
                    "NifTypes.BoundingVolume | None", 
                    "NifTypes.sInt | None"
                ]=None):
            self.p = parser
            if value == None:
                NifTypes.NiObjectNET.__init__(self, self.p)
                if validateVersion(self.p, [3]): 
                    self.Flags = self.p.u16Alt()
                self.Translation = self.p.vec3Alt()
                self.Rotation = self.p.matrix33Alt()
                self.Scale = self.p.singleAlt()
                if validateVersion(self.p, until=[4,2,2]):
                    self.Velocity = self.p.vec3Alt()
                self.Num_Properties = self.p.u32Alt()
                self.Properties = self.p.s32Alt(self.Num_Properties.value)
                if validateVersion(self.p, until=[2,3,0,0]):
                    self.Unknown_1 = self.p.u32Alt()
                    self.Unknown_2 = self.p.u8Alt()
                self.Has_Bounding_Volume = self.p.boolAlt()
                if validateVersion(self.p, [3], [4,2,2,0]): 
                    if self.Has_Bounding_Volume.value:
                        self.Bounding_Volume = NifTypes.BoundingVolume(self.p)
                if validateVersion(self.p, since=[10,0,1,0]):
                    self.Collision_Object = self.p.s32Alt()
                return
            self.set(value)
        def save(self):
            NifTypes.NiObjectNET.save(self)
            if validateVersion(self.p, [3]): 
                self.Flags.save()
            self.Translation.save()
            self.Rotation.save()
            self.Scale.save()
            if validateVersion(self.p, until=[4,2,2]):
                self.Velocity.save()
            self.Num_Properties.save()
            self.Properties.save()
            if validateVersion(self.p, until=[2,3,0,0]):
                self.Unknown_1.save()
                self.Unknown_2.save()
            self.Has_Bounding_Volume.save()
            if validateVersion(self.p, [3], [4,2,2,0]): 
                if self.Has_Bounding_Volume.value:
                    self.Bounding_Volume.save()
            if validateVersion(self.p, since=[10,0,1,0]):
                self.Collision_Object.save()
        def set(self, value:tuple[
                    "NifTypes.NiObjectNET",
                    "NifTypes.uShort | None", 
                    "NifTypes.Vector3", 
                    "NifTypes.Matrix33", 
                    "NifTypes.Single", 
                    "NifTypes.Vector3 | None", 
                    "NifTypes.uInt", 
                    list["NifTypes.sInt"], 
                    "NifTypes.uInt | None", 
                    "NifTypes.uByte | None", 
                    "NifTypes.Bool", 
                    "NifTypes.BoundingVolume | None", 
                    "NifTypes.sInt | None"
                ]):
            NifTypes.NiObjectNET.assign(self, value[0])
            if validateVersion(self.p, [3]): 
                self.Flags = value[1]
            self.Translation = value[2]
            self.Rotation = value[3]
            self.Scale = value[4]
            if validateVersion(self.p, until=[4,2,2]):
                self.Velocity = value[5]
            self.Num_Properties = value[6]
            self.Properties = value[7]
            if validateVersion(self.p, until=[2,3,0,0]):
                self.Unknown_1 = value[8]
                self.Unknown_2 = value[9]
            self.Has_Bounding_Volume = value[10]
            if validateVersion(self.p, [3], [4,2,2,0]): 
                if self.Has_Bounding_Volume.value:
                    self.Bounding_Volume = value[11]
            if validateVersion(self.p, since=[10,0,1,0]):
                self.Collision_Object = value[12]
        def assign(self, other:"NifTypes.NiAVObject"):
            NifTypes.NiObjectNET.assign(self, other)
            
            if validateVersion(self.p, [3]): 
                self.Flags = other.Flags
            self.Translation = other.Translation
            self.Rotation = other.Rotation
            self.Scale = other.Scale
            if validateVersion(self.p, until=[4,2,2]):
                self.Velocity = other.Velocity
            self.Num_Properties = other.Num_Properties
            self.Properties = other.Properties
            if validateVersion(self.p, until=[2,3,0,0]):
                self.Unknown_1 = other.Unknown_1
                self.Unknown_2 = other.Unknown_2
            self.Has_Bounding_Volume = other.Has_Bounding_Volume
            if validateVersion(self.p, [3], [4,2,2,0]): 
                if self.Has_Bounding_Volume.value:
                    self.Bounding_Volume = other.Bounding_Volume
            if validateVersion(self.p, since=[10,0,1,0]):
                self.Collision_Object = other.Collision_Object
    class NiExtraData:
        def __init__(self, parser, value:tuple[
            "NifTypes.SizedString | None",
            "NifTypes.sInt | None",
            "NifTypes.ByteArray | None",
            "Niftypes.uInt | None"
            ]=None):
            self.p = parser
            if value == None:
                if verifyVersion(self.p, since=[10,0,1]):
                    self.Name = self.p.stringAlt()
                if verifyVersion(self.p, until=[4,2,2]):
                    self.Next_Extra_Data = self.s32()
                if verifyVersion(self.p, until=[3,3,0,13]):
                    self.Extra_Data = NifTypes.ByteArray(self.p)
                if verifyVersion(self.p, since=[4], until=[4,2,2,0]):
                    self.Num_Bytes = self.p.u32()
                return
            self.set(value)
        def save(self):
            if verifyVersion(self.p, since=[10,0,1]):
                self.Name.save()
            if verifyVersion(self.p, until=[4,2,2]):
                self.Next_Extra_Data.save()
            if verifyVersion(self.p, until=[3,3,0,13]):
                self.Extra_Data.save()
            if verifyVersion(self.p, since=[4], until=[4,2,2,0]):
                self.Num_Bytes.save()
        def set(self, value:tuple[
            "NifTypes.SizedString | None",
            "NifTypes.sInt | None",
            "NifTypes.ByteArray | None",
            "Niftypes.uInt | None"
            ]):
            if verifyVersion(self.p, since=[10,0,1]):
                self.Name = value[0]
            if verifyVersion(self.p, until=[4,2,2]):
                self.Next_Extra_Data = value[1]
            if verifyVersion(self.p, until=[3,3,0,13]):
                self.Extra_Data = value[2]
            if verifyVersion(self.p, since=[4], until=[4,2,2,0]):
                self.Num_Bytes = value[3]
        def assign(self, other:"NifTypes.NiExtraData"):
            if verifyVersion(self.p, since=[10,0,1]):
                self.Name = other.Name
            if verifyVersion(self.p, until=[4,2,2]):
                self.Next_Extra_Data = other.Next_Extra_Data
            if verifyVersion(self.p, until=[3,3,0,13]):
                self.Extra_Data = other.Extra_Data
            if verifyVersion(self.p, since=[4], until=[4,2,2,0]):
                self.Num_Bytes = other.Num_Bytes
    
    # NiBlocks
    class NiNode(NiAVObject):
        def __init__(self, parser, value:tuple[
                "NifTypes.NiAVObject",
                "NifTypes.uInt",
                list["NifType.sInt"],
                "NifType.uInt",
                list["NifType.sInt"]
            ]=None):
            self.p = parser
            if value==None:
                NifTypes.NiAVObject.__init__(self, self.p)
                self.Num_Children = self.p.u32()
                self.Children = self.p.s32(self.Num_Chldren.value)
                self.Num_Effects = self.p.u32()
                self.Effects = self.p.s32(self.Num_Effects.value)
                return
            self.set(value)
        def save(self):
            NifTypes.NiAVObject.save(self)
            self.Num_Children.save()
            for i in range(self.Num_Children.value): self.Children[i].save()
            self.Num_Effects.save()
            for i in range(self.Num_Effects.value): self.Effects[i].save()
        def set(self, value:tuple[
                "NifTypes.NiAVObject",
                "NifTypes.uInt",
                list["NifType.sInt"],
                "NifType.uInt",
                list["NifType.sInt"]
            ]):
            NifTypes.NiAVObject.assign(self, value[0])
            self.Children = value[1]
            self.Num_Children = value[2]
            self.Effects = value[3]
            self.Num_Children = value[4]
        def assign(self, other:"NifTypes.NiNode"):
            NifTypes.NiAVObject.assign(self, other)
            
            self.Children = other.Children
            self.Num_Children = other.Num_Children
            self.Effects = other.Effects
            self.Num_Children = other.Num_Children
    class NiStringExtraData(NiExtraData):
        def __init__(self, parser, value:tuple[
                "NifTypes.NiExtraData",
                "NifTypes.SizedString"
            ]=None):
            self.p = parser
            if value == None:
                NifTypes.NiExtraData.__init__(self, self.p)
                if verifyVersion(self.p, since=[4]):
                    self.String_Data = self.p.stringAlt()
                return
            self.set(value)
        def save(self):
            NifTypes.NiExtraData.save(self)
            if verifyVersion(self.p, since=[4]):
                self.String_Data.save()
        def set(self, value:tuple[
                "NifTypes.NiExtraData",
                "NifTypes.SizedString"
            ]):
            NifTypes.NiExtraData.assign(self, value[0])
            if verifyVersion(self.p, since=[4]):
                self.String_Data = value[1]
        def assign(self, other:"NifTypes.NiStringExtraData"):
            NifTypes.NiExtraData.assign(self, other)
            if verifyVersion(self.p, since=[4]):
                self.String_Data = other.String_Data


class NetImmerseFileParser:
    # StUpiD
    def open_file_dialog(title = "Select a Nif File"):
        if not __name__ == "__main__":
            return None
        #Cant control this windows location because reasons... how anoying. I HATE WINDOWS DEFAULT LOCATION
        # And im not crating a custom gui because i dont feel like it, it shouldnt be nessasary
        file_path = filedialog.askopenfilename(title=title, filetypes=[
            ("NIF, KF (Supported Files)", ("*.nif" or "*.kf")),
            ("NIF (Net-Immerse File format)", "*.nif"),
            ("KF (Key Frame)", "*.kf"),
            ("Any Files", "*.*")
        ])
        if file_path:
            return file_path
        else: return None

    def validateVersion(version, since:list = None, until:list = None):
        if since == None and until == None: # if both, somethings wrong
            raise Exception("Version Validation Error: validateVersion requires at least a 'since' or 'until' to have a value")
        
        VersLenException = False

        if len(version) != 4:
            VersLenException = True
        if since != None:
            if len(since) != 4:
                if len(since) < 4:
                    while len(since) < 4:
                        since.append(0)
                else:
                    VersLenException = True
        if until != None:
            if len(until) != 4:
                if len(until) < 4:
                    while len(until) < 4:
                        until.append(0)
                else:
                    VersLenException = True
        
        if VersLenException: 
            raise Exception("Version Error: Version lists must consist of no more than 4 elements")
                
        
        
        if until == None:
            return NetImmerseFileParser.compareVersions(version, since) >= 0
            
        if since == None:
            return NetImmerseFileParser.compareVersions(version, until) <= 0
    
        else: 
            if until == since:
                return version == since
            test1 = NetImmerseFileParser.compareVersions(version, until) <= 0
            test2 = NetImmerseFileParser.compareVersions(version, since) >= 0
            
            return test1 and test2
    
    def compareVersions(v1_parts, v2_parts):
        # Compare each part
        for i in range(max(len(v1_parts), len(v2_parts))):
            v1_part = v1_parts[i] if i < len(v1_parts) else 0
            v2_part = v2_parts[i] if i < len(v2_parts) else 0

            if v1_part < v2_part:
                return -1
            elif v1_part > v2_part:
                return 1

        return 0
    
    # Factories
    class Base:
        file = None 
        data = {}
        
        def arr(self, f, n, save=False, value=None):
            if save:
                for i in range(n):
                    self.file.write(struct.pack(f, value[i]))
                return
            return [f() for _ in range(n)]
            #l = []
            #for i in range(n):
            #    l.append(f())
            #return l

        def u32Alt(self, n=1, save=False, value=None):
            if save:
                if n == 1:
                    value.save(parser)
                    return
                for i in range(n): value[i].save(parser)
                return
            if n == 1: return NifTypes.uInt(parser)
            return [NifTypes.uInt(parser) for _ in range(n)]
        def u32(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.file.write(struct.pack('<I', value))
                    return
                self.arr('<I', n, save, value)
                return
            if n == 1:
                return struct.unpack('<I', self.file.read(4))[0]
            return self.arr(self.u32, n)
        
        def s32Alt(self, n=1, save=False, value=None):
            if save:
                if n == 1:
                    value.save(parser)
                    return
                for i in range(n): value[i].save(parser)
                return
            if n == 1: return NifTypes.sInt(parser)
            return [NifTypes.sInt(parser) for _ in range(n)] 
        def s32(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.file.write(struct.pack('<i', value))
                    return
                self.arr('<i', n, save, value)
                return
                for i in range(n): 
                    self.file.write(struct.pack('<i', value))
                return
            if n == 1:
                return struct.unpack('<i', self.file.read(4))[0]
            return self.arr(self.s32, n)

        def u16Alt(self, n=1, save=False, value=None):
            if save:
                if n == 1:
                    value.save(parser)
                    return
                for i in range(n): value[i].save(parser)
                return
            if n == 1: return NifTypes.uShort(parser)
            return [NifTypes.uShort(parser) for _ in range(n)]
        def u16(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.file.write(struct.pack('<H', value))
                    return
                self.arr('<H', n, save, value)
                return
            if n == 1: 
                return struct.unpack('<H', self.file.read(2))[0]
            return self.arr(self.u16, n)

        def s16Alt(self, n=1, save=False, value=None):
            if save:
                if n == 1:
                    value.save(parser)
                    return
                for i in range(n): value[i].save(parser)
                return
            if n == 1: return NifTypes.sShort(parser)
            return [NifTypes.sShort(parser) for _ in range(n)] 
        def s16(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.file.write(struct.pack('<h', value))
                    return
                self.arr('<h', n, save, value)
                return
            if n == 1:
                return struct.unpack('<h', self.file.read(2))[0]
            return self.arr(self.s16, n)

        def u8Alt(self, n=1, save=False, value=None):
            if save:
                if n == 1:
                    value.save(parser)
                    return
                for i in range(n): value[i].save(parser)
                return
            if n == 1: return NifTypes.uByte(parser)
            return [NifTypes.uByte(parser) for _ in range(n)]
        def u8(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.file.write(struct.pack('<B', value))
                    return
                self.arr('<B', n, save, value)
                return

            if n == 1:
                val = struct.unpack('<B', self.file.read(1))[0]
                return val
            return self.arr(self.u8, n)

        def s8Alt(self, n=1, save=False, value=None):
            if save:
                if n == 1:
                    value.save(parser)
                    return
                for i in range(n): value[i].save(parser)
                return
            if n == 1: return NifTypes.sByte(parser)
            return [NifTypes.sByte(parser) for _ in range(n)]
        def s8(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.file.write(struct.pack('<b', value))
                    return
                self.arr('<b', n, save, value)
                return
            if n == 1:
                val = struct.unpack('<b', self.file.read(1))[0]
                return val
            return self.arr(self.s8, n)

        def char(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    value.save(parser)
                    return
                for i in range(n):
                    value[i].save(parser)
                return
            if n == 1: return NifTypes.Char(self)
            return [NifTypes.Char(self) for _ in range(n)]

        def boolAlt(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    value.save()
                    return
                for i in range(n): value[i].save()
                return
            if n == 1: return NifTypes.Bool(parser)
            return [NifTypes.Bool(parser) for _ in range(n)]
        def bool(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.u32(save=True, value=int(0x7FFFFF) if value else 0) # weird bools in nif 3.3.0.13
                    return
                for i in range(n):
                    self.bool(save=True, value=value[i])
                return
            if n == 1:
                return True if self.u32() > 0 else False
            self.arr(self.bool, n)

        def singleAlt(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    value.save()
                    return
                for i in range(n): value[i].save()
                return
            if n == 1: return NifTypes.Single(parser)
            return [NifTypes.Single(parser) for _ in range(n)]
        
        def single(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.file.write(struct.pack('<f', value))
                    return
                self.arr('<f', n, True, value)
                return
            if n == 1:
                return struct.unpack('<f', self.file.read(4))[0]
            return self.arr(self.single, n)

        def doubleAlt(self, n = 1, save=False, valuie=None):
            if save:
                if n == 1:
                    value.save()
                    return
                for i in range(n): value[i].save()
                return
            if n == 1: return NifTypes.Double(parser)
            return [NifTypes.Double(parser) for _ in range(n)]
        def double(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.file.write(struct.pack('<d', value))
                    return
                self.arr('<d', n, True, value)
                return
            if n == 1: return struct.unpack('<d', self.file.read(8))[0]
            return self.arr(self.double, n)
 
        def stringAlt(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    value.save(self)
                    return
                for i in range(n): value[i].save(self)
                return
            if n == 1: return NifTypes.SizedString(self)
            return [NifTypes.SizedString(self) for _ in range(n)]           
        def string(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.u32(save=True, value=value[0])
                    if value[0] > 0:
                        self.file.write(value[1])
                    return
                for i in range(n):
                    self.string(save=True, value=value[i])
                return
            if n == 1:
                s = [self.u32()]
                s.append(self.file.read(s[0]))
                return s
            return self.arr(self.string, n)
        
        def extraDataStringAlt(self, save=False, value=None):
            if save:
                value.save(self)
                return
            return NifTypes.ExtraDataString(self)
        def extraDataString(self, save=False, value=None):
            if save:
                self.u32(save=True, value=value[0])
                if value[0] > 0:
                    self.string(save=True, value=value[1])
                return
            b = [self.u32()]
            if b[0] > 0:
                b.append(self.string())
            return b
        
        def byteArrayAlt(self, save=False, value=None):
            if save:
                value.save(self)
                return
            return NifTypes.SizedBytes(self)
        def byteArray(self, save=False, value=None):
            if save:
                self.u32(save=save, value=value[0])
                self.u8(n=value[0], save=save, value=value[2])
                return
            block = [
                self.u32(),#Length
            ]
            block.append(
                self.u8(block[0])
            )
            return block
            #b = {
            #    "Length" : self.s32()
            #}
            #b["bytes"] = []
            #for byte in range(b["Length"]):
            #    b["bytes"].append(hex(self.u8()))
            #return b
        
        # semi-primitive
        def vec2Alt(self, n = 1, save=False, value=None):
            if save:
                if n==1:
                    value.save(self)
                    return
                for i in range(n):
                    value[i].save(self)
                return
            if n == 1: return NifTypes.Vector2(self)
            return [NifTypes.Vector2(self) for _ in range(n)]
        def vec2(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.single(2, True, value)
                else:
                    for i in range(n):
                        self.vec2(save=True, value=value[i])
                return
            if n == 1: 
                return self.single(2)
            return self.arr(self.vec2, n)

        def vec3Alt(self, n = 1, save=False, value=None):
            if save:
                if n==1:
                    value.save(self)
                    return
                for i in range(n):
                    value[i].save(self)
                return
            if n == 1: return NifTypes.Vector3(self)
            return [NifTypes.Vector3(self) for _ in range(n)]
        def vec3(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.single(3, True, value)
                else:
                    for i in range(n):
                        self.vec3(save=True, value=value[i])
                return
            if n == 1: 
                return self.single(3)
            return self.arr(self.vec3, n)

        def vec4Alt(self, n = 1, save=False, value=None):
            if save:
                if n==1:
                    value.save(self)
                    return
                for i in range(n):
                    value[i].save(self)
                return
            if n == 1: return NifTypes.Vector4(self)
            return [NifTypes.Vector4(self) for _ in range(n)]
        def vec4(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.single(4, True, value)
                else:
                    for i in range(n):
                        self.vec4(save=True, value=value[i])
                return
            if n == 1: 
                return self.single(4)
            return self.arr(self.vec4, n)

        def u16vec2Alt(self, n = 1, save=False, value=None):
            if save:
                if n==1:
                    value.save(self)
                else:
                    for i in range(n):
                        value[i].save(self)
                return
            if n == 1: return NifTypes.u16Vector2(self)
            return [NifTypes.u16Vector2(self) for _ in range(n)]
        def u16vec2(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.u16(2, True, value)
                else:
                    for i in range(n):
                        self.u16vec2(save=True, value=value[i])
                return
            if n == 1: 
                return self.u16(2)
            return self.arr(self.u16vec2, n)

        def u16vec3Alt(self, n = 1, save=False, value=None):
            if save:
                if n==1:
                    value.save(self)
                else:
                    for i in range(n):
                        value[i].save(self)
                return
            if n == 1: return NifTypes.u16Vector3(self)
            return [NifTypes.u16Vector3(self) for _ in range(n)]
        def u16vec3(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.u16(3, True, value)
                else:
                    for i in range(n):
                        self.u16vec3(save=True, value=value[i])
                return
            if n == 1: 
                return self.u16(3)
            return self.arr(self.u16vec3, n)

        def u16vec4Alt(self, n = 1, save=False, value=None):
            if save:
                if n==1:
                    value.save(self)
                else:
                    for i in range(n):
                        value[i].save(self)
                return
            if n == 1: return NifTypes.u16Vector4(self)
            return [NifTypes.u16Vector4(self) for _ in range(n)]
        def u16vec4(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.u16(4, True, value)
                else:
                    for i in range(n):
                        self.u16vec4(save=True, value=value[i])
                return
            if n == 1: 
                return self.u16(4)
            return self.arr(self.u16vec4, n)

        def u8vec4Alt(self, n = 1, save=False, value=None):
            if save:
                if n==1:
                    value.save(self)
                else:
                    for i in range(n):
                        value[i].save(self)
                return
            if n == 1: return NifTypes.u8Vector4(self)
            return [NifTypes.u8Vector4(self) for _ in range(n)]
        def u8vec4(self, n = 1, save = False, value=None):
            if save:
                if n == 1:
                    self.u8(4, save=True, value=value)
                else:
                    for i in range(n):
                        self.u8vec4(save=True, value=value[i])
                return
            if n == 1:
                return self.u8(4)
            return self.arr(self.u8vec4, n)

        # semi-complex
        def matrix33Alt(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    value.save()
                    return
                for i in range(n): value[i].save()
                return
            if n == 1: return NifTypes.Matrix33(self)
            return [NifTypes.Matrix33(self) for _ in range(n)]
        def matrix33(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.vec3(3, True, value)
                    return
                for i in range(n):
                    self.matrix33(save=True, value=value[i])
                return
            if n == 1:
                return self.vec3(3)

            return self.arr(self.matrix33, n)

        def matrix22Alt(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    value.save()
                    return
                for i in range(n): value[i].save()
                return
            if n == 1: return NifTypes.Matrix22(self)
            return [NifTypes.Matrix22(self) for _ in range(n)]
        def matrix22(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.vec2(2, True, value)
                else:
                    for i in range(n):
                        self.matrix22(save=True, value=value[i])
                return
            if n == 1:
                return self.vec2(2)
            return self.arr(self.matrix22, n)

        def headerAlt(self, save=False, value=None):
            if save:
                value.save(self)
                return
            return NifTypes.Header(self)
        def header(self, save=False, value=None):
            if save:
                self.file.write(value["Header"] + b'\n')
                self.u8(n=4, save=True, value=value["Version"].reversed())
                self.u32(save=True, value=value["Num Blocks"])
                return
            buffer = b''
            b = self.file.read(1)
            while not b == b'\n':
                buffer += b
                b = self.file.read(1)
            block =  {
                "Header" : buffer,
                "Version" : mylist(self.s8(4)).reversed(),
                "Num Blocks" : self.u32() # little endian uInt32
            }


            return block

        def footerAlt(self, save=False, value=None):
            if save:
                value.save(self)
                return
            return NifTypes.Footer(self)
        def footer(self, save=False, value=None):
            if save:
                self.u32(save=True, value=value["Num Roots"])
                self.s32(value["Num Roots"], save=True, value=value["Roots"])
                return
            footer = {
                "Num Roots" : self.u32()
            }
            footer["Roots"] = self.s32(footer["Num Roots"])
            return footer

    class BlockParts(Base):
        # complex
        
             
        
        class cMipMap:
            def __init__(self, parser):
                self.Width = parser.u32()
                self.Height = parser.u32()
                self.Offset = parser.u32()
            def save(self, parser):
                parser.u32(save=True,value=self.Width)
                parser.u32(save=True,value=self.Height)
                parser.u32(save=True,value=self.Offset)
        
        def MipMapAlt(self, n=1, save=False, value=None):
            if save:
                if n == 1:
                    value.save(self)
                    return
                for i in range(n): value[i].save(self)
                return
            if n == 1:
                return self.cMipMap(self)
            return [self.cMipMap(self) for _ in range(n)]
            #return self.arr(self.MipMapAlt, n)
            
        def MipMap(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.u32(save=True, value=value["Width"])
                    self.u32(save=True, value=value["Height"])
                    self.u32(save=True, value=value["Offset"])
                    return
                for i in range(n):
                    self.MipMap(save=True, value=value[i])
                return
            if n == 1: 
                return {
                    "Width" : self.u32(),
                    "Height" : self.u32(),
                    "Offset" : self.u32()
                }
            return self.arr(self.MipMap, n)

        def TexDesc(self, save=False, value=None):

            if save:
                self.s32(save=save, value=value["Source"])
                self.u32(save=save, value=value["Clamp Mode"])
                self.u32(save=save, value=value["Filter Mode"])
                self.u32(save=save, value=value["UV Set"])
                self.s16(save=save, value=value["PS2 L"])
                self.s16(save=save, value=value["PS2 K"])
                self.u16(save=save, value=value["unknown Short 1"])
                return
            return {
                "Source" : self.s32(),
                "Clamp Mode" : self.u32(),
                "Filter Mode" : self.u32(),
                "UV Set" : self.u32(),
                "PS2 L" : self.s16(),
                "PS2 K" : self.s16(),
                "unknown Short 1" : self.u16()
            }

        def MatchGroup(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.u16(save=True, value=value["Num Vertices"])
                    self.u16(value["Num Vertices"], save=True, value=value["Vertex Indices"])
                else:
                    for i in range(n):
                        self.MatchGroup(save=True, value=value[i])
                return
            if n == 1:
                mg = {}
                mg["Num Vertices"]   = self.u16()
                mg["Vertex Indices"] = self.u16(mg["Num Vertices"])
                return mg
            return self.arr(self.MatchGroup, n)

        def VertexWeight(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.u16(save=True, value=value["Index"])
                    self.single(save=True, value=value["Weight"])
                else:
                    for i in range(n):
                        self.VertexWeight(save=True, value=value[i])
                return
            if n == 1:
                return {
                    "Index" : self.u16(),
                    "Weight" : self.single()
                }
            return self.arr(self.VertexWeight, n)

        def NiTransform(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.matrix33(save=True, value=value["Rotation"])
                    self.vec3(save=True, value=value["Translatrion"])
                    self.single(save=True, value=value["Scale"])
                else:
                    for i in range(n):
                        self.NiTransform(save = True, value=value[i])
                return

            if n == 1:
                return {
                    "Rotation" : self.matrix33(),
                    "Translatrion" : self.vec3(),
                    "Scale" : self.single()
                }
            return self.arr(self.NiTransform, n)

        def Bone(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.NiTransform(save=True, value=value["Skin Transform"])
                    self.vec3(save=True, value=value["Bounding Sphere"]["Center"])
                    self.single(save=True, value=value["Bounding Sphere"]["Radius"])
                    self.u16(save=True, value=value["Num Vertices"])
                    self.VertexWeight(value["Num Vertices"], save=True, value=value["Vertex Weights"])
                else:
                    for i in range(n):
                        self.Bone(save=True, value=value[i])
                return

            if n == 1:
                b = {
                    "Skin Transform" : self.NiTransform(),
                    "Bounding Sphere" : {
                        "Center" : self.vec3(),
                        "Radius" : self.single()
                    },
                    "Num Vertices" : self.u16()
                }
                b["Vertex Weights"] = self.VertexWeight(b["Num Vertices"])
                return b
            return self.arr(self.Bone, n)

        def BoundingVolume(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.s32(save=True, value=value["Collision type"])
                    match(value["Collision type"]):
                        case 0: # Sphere
                            self.vec3(save=True, value=value["Center"])
                            self.single(save=True, value=value["Radius"])
                        case 1: # Box
                            self.vec3(save=True, value=value["Center"])
                            self.vec3(save=True, value=value["Axis"])
                            self.vec3(save=True, value=value["Extent"])
                        case 2: # Capsule
                            self.vec3(save=True, value=value["Center"])
                            self.vec3(save=True, value=value["Origin"])
                            self.single(save=True, value=value["Extent"])
                            self.single(save=True, value=value["Radius"])
                        case 5: # Half Space
                            self.vec3(save=True, value=value["Plane"]["Normal"])
                            self.single(save=True, value=value["Plane"]["Constant"])
                            self.vec3(save=True, value=value["Center"])
                else:
                    for i in range(n):
                        self.BoundingVolume(save=True, value=value[i])
                return


            if n == 1:
                bv = {}
                bv["Collision Type"] = self.u32()
                match(bv["Collision Type"]):
                    case 0: # sphere
                        bv["Sphere"] = {
                            "Center" : self.vec3(),
                            "Radius" : self.single()
                        }
                    case 1: # Box
                        bv["Box"] = {
                            "Center" : self.vec3(),
                            "Axis" : self.vec3(3),
                            "Extent" : self.vec3()
                        }
                    case 2: # capsule
                        bv["Capsule"] = {
                            "Center" : self.vec3(),
                            "Origin" : self.vec3(),
                            "Extent" : self.single(),
                            "Radius" : self.single()
                        }
                    case 4: # Union; no data
                        pass
                    case 5: # Half Space
                        bv["Half Space"] = {
                            "Plane" : {
                                "Normal" : self.vec3(),
                                "Constant" : self.single()
                            },
                            "Center" : self.vec3()
                        }
                return bv
            return self.arr(BoundingVolume, n)

        def QuaternionKey(self, n = 1, arg = 0, save=False, value=None):
            if save:
                if n == 1:
                    self.single(save=True, value=value["Time"])
                    if arg != 4:
                        self.vec4(save=True, value=value["Value"])
                    if arg == 3:
                        self.vec3(save=True, value=value["TBC"])
                else:    
                    for i in range(n):
                        self.QuaternionKey(arg=arg, save=True, value=value[i])
                return
            if n == 1: 
                qk = {
                    "Time" : self.single(),
                }
                if arg != 4: 
                    qk["Value"] = self.vec4()
                if arg == 3: 
                    qk["TBC"] = self.vec3()
                return qk
            ls = []
            for i in range(n):
                ls.append(self.QuaternionKey(arg=arg))
            return ls

        def Key(self, typefunc, n = 1, arg = 0, save=False, value=None):
            if save:
                if n == 1:
                    self.single(save=True, value=value["Time"])
                    typefunc(save=True, value=value["Value"])
                    if arg == 2:
                        typefunc(save=True, value=value["Forward"])
                        typefunc(save=True, value=value["Backward"])
                    if arg == 3:
                        self.vec3(save=True, value=value["TBC"])
                else:    
                    for i in range(n):
                        self.Key(typefunc, arg=arg, save=True, value=value[i])
                return
            if n == 1:
                k = {
                    "Time" : self.single(),
                    "Value" : typefunc()
                }
                if arg == 2: 
                    k["Forward"] = typefunc()
                    k["Backward"] = typefunc()
                if arg == 3: 
                    k["TBC"] = self.vec3()
                return k
            ls = []
            for i in range(n): ls.append(self.Key(typefunc, arg=arg))
            return ls

        def KeyGroup(self, typefunc, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.u32(save=True, value=value["Num Keys"])
                    if value["Num Keys"] != 0:
                        self.u32(save=True, value=value["Interpolation"])
                    self.Key(typefunc, value["Num Keys"], value.get("Interpolation", 0), save=True, value=value["Keys"])
                else:
                    for i in range(n):
                        self.KeyGroup(typefunc, save=True, value=value[i])
                return
            if n == 1:
                kg = {
                    "Num Keys" : self.u32()
                }
                if kg["Num Keys"] != 0: 
                    kg["Interpolation"] = self.u32()

                kg["Keys"] = self.Key(typefunc, kg["Num Keys"], kg.get("Interpolation", 0))
                return kg
            ls = []
            for i in range(n): ls.append(self.KeyGroup(typefunc))
            return ls

        def NiParticleInfo(self, n = 1, save=False, value=None):
            if save:
                if n == 1:
                    self.vec3(save=True, value=value["Velocity"])
                    self.vec3(save=True, value=value["Rotation Axis"])
                    self.single(save=True, value=value["Age"])
                    self.single(save=True, value=value["Life Span"])
                    self.single(save=True, value=value["Last Update"])
                    self.u16(save=True, value=value["Spawn Generation"])
                    self.u16(save=True, value=value["Code"])
                else:
                    ls = []
                    for i in range(n):
                        ls.append(self.NiParticleInfo(save=True, value=value[i]))
                return
            
            if n == 1:
                return {
                    "Velocity" : self.vec3(),
                    "Rotation Axis" : self.vec3(),
                    "Age" : self.single(),
                    "Life Span" : self.single(),
                    "Last Update" : self.single(),
                    "Spawn Generation" : self.u16(),
                    "Code" : self.u16()
                }
            else:
                ls = []
                for i in range(n):
                    ls.append(self.NiParticleInfo())
                return ls
            
    class NiBlocks(BlockParts):

        def NiStringExtraData(self, save=False, value=None):
            if save:
                self.s32(save=True, value=value["Next Extra Data"])
                self.u32(save=True, value=value["Extra Data"][0])
                if value["Extra Data"][0] > 0:
                    self.string(save=True, value=value["Extra Data"][1])
                return
            return { 
                "Next Extra Data" : self.s32(),
                "Extra Data" : [self.u32(), self.string()]#self.bytearr()
            }

            return block

        def NiKeyframeController(self, save=False, value=None):
            if save:
                self.s32(save=True, value=value["Next Controller"])
                self.u16(save=True, value=value["Flags"])
                self.single(save=True, value=value["Frequency"])
                self.single(save=True, value=value["Phase"])
                self.single(save=True, value=value["Start Time"])
                self.single(save=True, value=value["Stop Time"])
                if NetImmerseFileParser.validateVersion(self.data["header"]["Version"], [3,3,0,13], [10,1,0,103]):
                    self.s32(save=True, value=value["Target"])
                self.s32(save=True, value=value["Data"])
                return
            block = {}
            block["Next Controller"] = self.s32()
            block["Flags"] = self.u16()
            block["Frequency"] = self.single()
            block["Phase"] = self.single()
            block["Start Time"] = self.single()
            block["Stop Time"] = self.single()
            if NetImmerseFileParser.validateVersion(self.data["header"]["Version"], [3,3,0,13], [10,1,0,103]):
                block["Target"] = self.s32()
            block["Data"] = self.s32()
            return block
        
        def NiNode(self, save=False, value=None):
            if save:
                self.string(save=True, value=value["Name"])
                self.s32(save=True, value=value["Extra Data"])
                self.s32(save=True, value=value["Controller"])
                self.u16(save=True, value=value["Flags"])
                self.vec3(save=True, value=value["Translation"])
                self.matrix33(save=True, value=value["Rotation"])
                self.single(save=True, value=value["Scale"])
                self.vec3(save=True, value=value["Velocity"])
                self.u32(save=True, value=value["Num Properties"])
                self.s32(value["Num Properties"], save=True, value=value["Properties"])
                self.bool(save=True, value=value["Has Bounding Volume"])
                if value["Has Bounding Volume"]:
                    self.BoundingVolume(save=True, value=value["Bounding Volume"])
                self.u32(save=True, value=value["Num Children"])
                self.s32(value["Num Children"], save=True, value=value["Children"])
                self.u32(save=True, value=value["Num Effects"])
                self.s32(value["Num Effects"], save=True, value=value["Effects"])
                return
            block = { 
                "Name" : self.string(),
                "Extra Data" : self.s32(),
                "Controller" : self.s32(),
                "Flags" : self.u16(),
                "Translation" : self.vec3(),
                "Rotation" : self.matrix33(),
                "Scale" : self.single(),
                "Velocity" : self.vec3(),
                "Num Properties" : self.u32(),
                "Properties" : []
            }
            block["Properties"] = self.s32(block["Num Properties"])
            block["Has Bounding Volume"] = self.bool()
            if block["Has Bounding Volume"] == True:
                block["Bounding Volume"] = self.BoundingVolume()
            block["Num Children"] = self.u32()
            block["Children"] = self.s32(block["Num Children"])
            block["Num Effects"] = self.u32()
            block["Effects"] = self.s32(block["Num Effects"])
            return block

        def NiZBufferProperty(self, save=False, value=None):
            if save:
                self.string(save=True, value=value["Name"])
                self.s32(save=True, value=value["Extra Data"])
                self.s32(save=True, value=value["Controller"])
                self.u16(save=True, value=value["Flags"])
                return
            return { 
                "Name" : self.string(),
                "Extra Data" : self.s32(),
                "Controller" : self.s32(),
                "Flags" : self.u16()
            }

        def NiVertexColorProperty(self, save=False, value=None):
            if save:
                self.string(save=True, value=value["Name"])
                self.s32(save=True, value=value["Extra Data"])
                self.s32(save=True, value=value["Controller"])
                self.u16(save=True, value=value["Flags"])
                self.u32(save=True, value=value["Vertex Mode"])
                self.u32(save=True, value=value["Lighting Mode"])
                return
            return { 
                "Name" : self.string(),
                "Extra Data" : self.s32(),
                "Controller" : self.s32(),
                "Flags" : self.u16(),
                "Vertex Mode": self.u32(),
                "Lighting Mode": self.u32()
            }

        def NiMaterialProperty(self, save=False, value=None):
            if save:
                self.string(save=True, value=value["Name"])
                self.s32(save=True, value=value["Extra Data"])
                self.s32(save=True, value=value["Controller"])
                self.u16(save=True, value=value["Flags"])
                self.vec3(save=True, value=value["Ambient Color"])
                self.vec3(save=True, value=value["Diffuse Color"])
                self.vec3(save=True, value=value["Specular Color"])
                self.vec3(save=True, value=value["Emissive Color"])
                self.single(save=True, value=value["Glossiness"])
                self.single(save=True, value=value["Alpha"])
                return
            return { 
                "Name" : self.string(),
                "Extra Data" : self.s32(),
                "Controller" : self.s32(),
                "Flags" : self.u16(),
                "Ambient Color" : self.vec3(),
                "Diffuse Color" : self.vec3(),
                "Specular Color" : self.vec3(),
                "Emissive Color" : self.vec3(),
                "Glossiness" : self.single(),
                "Alpha": self.single(),
            }

        def NiTexturingProperty(self, save=False, value=None):
            if save:
                self.string(save=True, value=value["Name"])
                self.s32(save=True, value=value["Extra Data"])
                self.s32(save=True, value=value["Controller"])
                self.u16(save=True, value=value["Flags"])
                self.u32(save=True, value=value["Apply Mode"])
                self.u32(save=True, value=value["Texture Count"])

                self.bool(save=True, value=value["Has Base Texture"])
                if value["Has Base Texture"]:
                    self.TexDesc(save=True, value=value["Base Texture"])

                self.bool(save=True, value=value["Has Dark Texture"])
                if value["Has Dark Texture"]:
                    self.TexDesc(save=True, value=value["Dark Texture"])

                self.bool(save=True, value=value["Has Detail Texture"])
                if value["Has Detail Texture"]:
                    self.TexDesc(save=True, value=value["Detail Texture"])

                self.bool(save=True, value=value["Has Gloss Texture"])
                if value["Has Gloss Texture"]:
                    self.TexDesc(save=True, value=value["Gloss Texture"])

                self.bool(save=True, value=value["Has Glow Texture"])
                if value["Has Glow Texture"]:
                    self.TexDesc(save=True, value=value["Glow Texture"])

                if value["Texture Count"] > 5:
                    self.bool(save=True, value=value["Has Bump Map Texture"]) 
                    if value["Has Bump Map Texture"]:
                        self.TexDesc(save=True, value=value["Bump Map Texture"])
                        self.single(save=True, value=value["Bump Map Luma Scale"])
                        self.single(save=True, value=value["Bump Map Luma Offset"])
                        self.matrix22(save=True, value=value["Bump Map Matrix"])
                if value["Texture Count"] > 6:
                    self.bool(save=True, value=value["Has Decal 0 Texture"])
                    if value["Has Decal 0 Texture"]:
                        self.TexDesc(save=True, value=value["Decal 0"])
                if value["Texture Count"] > 7:
                    self.bool(save=True, value=value["Has Decal 1 Texture"])
                    if value["Has Decal 1 Texture"]:
                        self.TexDesc(save=True, value=value["Decal 1"])
                if value["Texture Count"] > 8:
                    self.bool(save=True, value=value["Has Decal 2 Texture"])
                    if value["Has Decal 2 Texture"]:
                        self.TexDesc(save=True, value=value["Decal 2"])
                if value["Texture Count"] > 9:
                    self.bool(save=True, value=value["Has Decal 3 Texture"])
                    if value["Has Decal 3 Texture"]:
                        self.TexDesc(save=True, value=value["Decal 3"])
                return
            block = {
                "Name" : self.string(),
                "Extra Data" : self.s32(),
                "Controller" : self.s32(),
                "Flags" : self.u16(),
                "Apply Mode" : self.u32(),
                "Texture Count" : self.u32()
            }
            block["Has Base Texture"] = self.bool()
            if block["Has Base Texture"] == True:
                block["Base Texture"] = self.TexDesc()            
            block["Has Dark Texture"] = self.bool()
            if block["Has Dark Texture"] == True:
                block["Dark Texture"] = self.TexDesc()        
            block["Has Detail Texture"] = self.bool()
            if block["Has Detail Texture"] == True:
                block["Detail Texture"] = self.TexDesc()        
            block["Has Gloss Texture"] = self.bool()
            if block["Has Gloss Texture"] == True:
                block["Gloss Texture"] = self.TexDesc()        
            block["Has Glow Texture"] = self.bool()
            if block["Has Glow Texture"] == True:
                block["Glow Texture"] = self.TexDesc()

            if block["Texture Count"] > 5:
                block["Has Bump Map Texture"] = self.bool()
                if block["Has Bump Map Texture"] == True:
                    block["Bump Map Texture"] = self.TexDesc()
                    block["Bump Map Luma Scale"] = self.single()
                    block["Bump Map Luma Offset"] = self.single()
                    block["Bump Map Matrix"] = self.matrix22()
            if block["Texture Count"] > 6:
                block["Has Decal 0 Texture"] = self.bool()
                if block["Has Decal 0 Texture"] == True:
                    block["Decal 0"] = self.TexDesc()
            if block["Texture Count"] > 7:
                block["Has Decal 1 Texture"] = self.bool()
                if block["Has Decal 1 Texture"] == True:
                    block["Decal 1"] = self.TexDesc()
            if block["Texture Count"] > 8:
                block["Has Decal 2 Texture"] = self.bool()
                if block["Has Decal 2 Texture"] == True:
                    block["Decal 2"] = self.TexDesc()
            if block["Texture Count"] > 9:
                block["Has Decal 3 Texture"] = self.bool()
                if block["Has Decal 3 Texture"] == True:
                    block["Decal 3"] = self.TexDesc()
            return block

        def NiSourceTexture(self, save=False, value=None):
            if save:
                self.string(save=True, value=value["Name"])
                self.s32(save=True, value=value["Extra Data"])
                self.s32(save=True, value=value["Controller"])
                self.u8(save=True, value=value["Use External"])
                if value["Use External"] == 0:
                    self.u8(save=True, value=value["Use Internal"])
                elif value["Use External"] == 1:
                    self.string(save=True, value=value["File Name"])
                if value["Use External"] == 0 and value["Use Internal"] == 1:
                    self.s32(save=True, value=value["Pixel Data"])
                self.u32(save=True, value=value["Format Prefs"]["Pixel Layout"])
                self.u32(save=True, value=value["Format Prefs"]["Use Mipmaps"])
                self.u32(save=True, value=value["Format Prefs"]["Alpha Format"])
                self.u8(save=True, value=value["Is Static"])

                return
            block = {
                "Name" : self.string(),
                "Extra Data" : self.s32(),
                "Controller" : self.s32()
            }
            block["Use External"] = self.u8()
            if block["Use External"] == 0:
                block["Use Internal"] = self.u8()
            if block["Use External"] == 1:
                block["File Name"] = self.string()
            if block["Use External"] == 0 and block["Use Internal"] == 1:
                block["Pixel Data"] = self.s32()
            block["Format Prefs"] = {
                "Pixel Layout" : self.u32(),
                "Use Mipmaps" : self.u32(),
                "Alpha Format" : self.u32()
            }
            block["Is Static"] = self.u8()
            return block

        def NiPixelData(self, save=False, value=None):
            if save:
                self.u32(save=True, value=value["Pixel Format"])
                self.u32(save=True, value=value["Red Mask"])
                self.u32(save=True, value=value["Green Mask"])
                self.u32(save=True, value=value["Blue Mask"])
                self.u32(save=True, value=value["Alpha Mask"])
                self.u32(save=True, value=value["Bits Per Pixel"])
                self.u8(8, save=True, value=value["Old Fast Compare"])
                self.s32(save=True, value=value["Palette"])
                self.u32(save=True, value=value["Num Mipmaps"])
                self.u32(save=True, value=value["Bytes Per Pixel"])
                self.MipMap(value["Num Mipmaps"], save=True, value=value["Mipmaps"])
                self.u32(save=True, value=value["Num Pixels"])
                self.u8(value["Num Pixels"], save=True, value=value["Pixel Data"])
                return
            block = {
                "Pixel Format" : self.u32(),
                "Red Mask" : self.u32(),
                "Green Mask" : self.u32(),
                "Blue Mask" : self.u32(),
                "Alpha Mask" : self.u32(),
                "Bits Per Pixel" : self.u32(),
                "Old Fast Compare" : self.u8(8),
                "Palette" : self.s32(),
                "Num Mipmaps" : self.u32(),
                "Bytes Per Pixel" : self.u32()
            }
            block["Mipmaps"] = self.MipMap(block["Num Mipmaps"])
            block["Num Pixels"] = self.u32()
            block["Pixel Data"] = self.u8(block["Num Pixels"])
            return block

        def NiTriShape(self, save=False, value=None):
            if save:
                self.string(save=True, value=value["Name"])
                self.s32(save=True, value=value["Extra Data"])
                self.s32(save=True, value=value["Controller"])
                self.u16(save=True, value=value["Flags"])
                self.vec3(save=True, value=value["Translation"])
                self.matrix33(save=True, value=value["Rotation"])
                self.single(save=True, value=value["Scale"])
                self.vec3(save=True, value=value["Velocity"])
                self.u32(save=True, value=value["Num Properties"])
                self.s32(value["Num Properties"], save=True, value=value["Properties"])
                self.bool(save=True, value=value["Has Bounding Volume"])
                if value["Has Bounding Volume"]:
                    self.BoundingVolume(save=True, value=value["Bounding Volume"])
                self.s32(save=True, value=value["Data"])
                self.s32(save=True, value=value["Skin Instance"])
                return
            block = {
                "Name" : self.string(),
                "Extra Data" : self.s32(),
                "Controller" : self.s32(),
                "Flags" : self.u16(),
                "Translation" : self.vec3(),
                "Rotation" : self.matrix33(),
                "Scale" : self.single(),
                "Velocity" : self.vec3(),
                "Num Properties" : self.u32(),
                "Properties" : []
            }
            block["Properties"] = self.s32(block["Num Properties"])
            block["Has Bounding Volume"] = self.bool()
            if block["Has Bounding Volume"] == True:
                block["Bounding Volume"] = self.BoundingVolume()
            block["Data"] = self.s32()
            block["Skin Instance"] = self.s32()

            return block

        def NiTriShapeData(self, save=False, value=None):
            if save:
                self.u16(save=True, value=value["Num Vertices"])
                self.bool(save=True, value=value["Has Vertices"])
                if value["Has Vertices"]:
                    self.vec3(value["Num Vertices"], True, value["Vertices"])
                self.bool(save=True, value=value["Has Normals"])
                if value["Has Normals"]:
                    self.vec3(value["Num Vertices"], True, value["Normals"])
                self.vec3(save=True, value=value["Bounding Sphere"]["Center"])
                self.single(save=True, value=value["Bounding Sphere"]["Radius"])
                self.bool(save=True, value=value["Has Vertex Colors"])
                if value["Has Vertex Colors"]:
                    self.vec4(value["Num Vertices"], True, value["Vertex Colors"])
                self.u16(save=True, value=value["Data Flags"])
                self.bool(save=True, value=value["Has UV"])
                if value["Has UV"]:
                    for i in range(value["Data Flags"] & 63):
                        self.vec2(value["Num Vertices"], True, value["UV Sets"][i])
                self.u16(save=True, value=value["Num Triangles"])
                self.u32(save=True, value=value["Num Triangle Points"])
                self.u16vec3(value["Num Triangles"], True, value["Triangles"])
                self.u16(save=True, value=value["Num Match Groups"])
                self.MatchGroup(value["Num Match Groups"], True, value["Match Groups"])

                return
            block = {
                "Num Vertices" : self.u16(),
                "Has Vertices" : self.bool()
            }
            if block["Has Vertices"] == True:
                block["Vertices"] = self.vec3(block["Num Vertices"])

            block["Has Normals"] = self.bool()
            if block["Has Normals"] == True:
                block["Normals"] = self.vec3(block["Num Vertices"])

            block["Bounding Sphere"] = {
                "Center" : self.vec3(),
                "Radius" : self.single()
            }

            block["Has Vertex Colors"] = self.bool()
            if block["Has Vertex Colors"] == True:
                block["Vertex Colors"] = self.vec4(block["Num Vertices"])
            block["Data Flags"] = self.u16()
            block["Has UV"] = self.bool()
            if block["Has UV"] == True:
                block["UV Sets"] = []
                for i in range(block["Data Flags"] & 63):
                    block["UV Sets"].append(self.vec2(block["Num Vertices"]))
            block["Num Triangles"] = self.u16()
            block["Num Triangle Points"] = self.u32()        
            block["Triangles"] = self.u16vec3(block["Num Triangles"])
            block["Num Match Groups"] = self.u16()
            block["Match Groups"] = self.MatchGroup(block["Num Match Groups"])

            return block
        
        def NiAlphaProperty(self, save=False, value=None):
            if save:
                self.string(save=True, value=value["Name"])
                self.s32(save=True, value=value["Extra Data"])
                self.s32(save=True, value=value["Controller"])
                self.u16(save=True, value=value["Flags"])
                self.u8(save=True, value=value["Threshold"])
                return
            return {
                "Name" : self.string(),
                "Extra Data" : self.s32(),
                "Controller" : self.s32(),
                "Flags" : self.u16(),
                "Threshold" : self.u8()
            }

        def NiFogProperty(self, save=False, value=None):
            if save:
                self.string(save=True,value=value["Name"])
                self.s32(save=True,value=value["Extra Data"])
                self.s32(save=True,value=value["Controller"])
                self.u16(save=True,value=value["Flags"])
                self.float(save=True,value=value["Fog Depth"])
                self.vec3(save=True,value=value["Fog Color"])
                return
            return {
                "Name" : self.string(),
                "Extra Data" : self.s32(),
                "Controller" : self.s32(),
                "Flags" : self.u16(),
                "Fog Depth" : self.single(),
                "Fog Color" : self.vec3()
            }

        def NiSkinInstance(self, save=False, value=None):
            if save:
                self.s32(save=True, value=value["Data"])
                self.s32(save=True, value=value["Skeleton Root"])
                self.u32(save=True, value=value["Num Bones"])
                self.s32(value["Num Bones"], True, value["Bones"])

                return
            block = {
                "Data" : self.s32(),
                "Skeleton Root" : self.s32(),
                "Num Bones" : self.u32()
            }
            block["Bones"] = self.s32(block["Num Bones"])
            return block

        def NiSkinData(self, save=False, value=None):
            if save:
                self.NiTransform(save=True, value=value["Skin Transform"])
                self.u32(save=True, value=value["Num Bones"])
                self.Bone(value["Num Bones"], True, value["Bone List"])
                return
            block = {
                "Skin Transform" : self.NiTransform(),
                "Num Bones" : self.u32()
            }
            block["Bone List"] = self.Bone(block["Num Bones"])
            return block
            pass
        
        def NiPalette(self, save=False, value=None):
            if save:
                self.u8(save=True, value=value["Has Alpha"])    
                self.u32(save=True, value=value["Num Entries"])
                self.u8vec4(value["Num Entries"], save=True, value=value["Palette"])   
                return
            block = {}
            block["Has Alpha"] = self.u8()
            block["Num Entries"] = self.u32()
            block["Palette"] = self.u8vec4(block["Num Entries"])
            return block

        def NiSpecularProperty(self, save=False, value=None):
            if save:
                self.string(save=True, value=value["Name"])
                self.s32(save=True, value=value["Extra Data"])
                self.s32(save=True, value=value["Controller"])
                self.u16(save=True, value=value["Flags"])
                return
            return {
                "Name" : self.string(),
                "Extra Data" : self.s32(),
                "Controller" : self.s32(),
                "Flags" : self.u16()
            }

        def NiTextureEffect(self, save=False, value=None):
            if save:
                self.string(save=True, value=value["Name"])
                self.s32(save=True, value=value["Extra Data"])
                self.s32(save=True, value=value["Controller"])
                self.u16(save=True, value=value["Flags"])
                self.vec3(save=True, value=value["Translation"])
                self.matrix33(save=True, value=value["Rotation"])
                self.single(save=True, value=value["Scale"])
                self.vec3(save=True, value=value["Velocity"])
                self.u32(save=True, value=value["Num Properties"])
                self.s32(value["Num Properties"], save=True, value=value["Properties"])
                self.bool(save=True, value=value["Has Bounding Volume"])
                if value["Has Bounding Volume"]:
                    self.BoundingVolume(save=True, value=value["Bounding Volume"])
                self.u32(save=True, value=value["Num Affected Nodes"])
                self.s32(value["Num Affected Nodes"], save=True, value=value["Affected Nodes"])
                self.matrix33(save=True, value=value["Model Projection Matrix"])
                self.vec3(save=True, value=value["Model Projection Translation"])
                self.u32(save=True, value=value["Texture Filtering"])
                self.u32(save=True, value=value["Texture Clamping"])
                self.u32(save=True, value=value["Texture Type"])
                self.u32(save=True, value=value["Coordinate Generation Type"])
                self.s32(save=True, value=value["Source Texture"])
                self.u8(save=True, value=value["Enable Plane"])
                self.vec3(save=True, value=value["Plane"]["Normal"])
                self.single(save=True, value=value["Plane"]["Constant"])
                self.s16(save=True, value=value["PS2 L"])
                self.s16(save=True, value=value["PS2 K"])
                self.u16(save=True, value=value["unknown short"])
                return
            block = {
                "Name" : self.string(),
                "Extra Data" : self.s32(),
                "Controller" : self.s32(),
                "Flags" : self.u16(),
                "Translation" : self.vec3(),
                "Rotation" : self.matrix33(),
                "Scale" : self.single(),
                "Velocity" : self.vec3()
            }
            block["Num Properties"] = self.u32()
            block["Properties"] = self.s32(block["Num Properties"])
            block["Has Bounding Volume"] = self.bool()
            if block["Has Bounding Volume"]:
                block["Bounding Volume"] = self.BoundingVolume()
            block["Num Affected Nodes"] = self.u32()
            block["Affected Nodes"] = self.s32(block["Num Affected Nodes"])
            block["Model Projection Matrix"] = self.matrix33()
            block["Model Projection Translation"] = self.vec3()
            block["Texture Filtering"] = self.u32()
            block["Texture Clamping"] = self.u32()
            block["Texture Type"] = self.u32()
            block["Coordinate Generation Type"] = self.u32()
            block["Source Texture"] = self.s32()
            block["Enable Plane"] = self.u8()
            block["Plane"] = {
                "Normal" : self.vec3(),
                "Constant" : self.single()
            }
            block["PS2 L"] = self.s16()
            block["PS2 K"] = self.s16()
            block["unknown short"] = self.u16()
            return block

        def NiBillboardNode(self, save=False, value=None):
            if save:
                self.string(save=True, value=value["Name"])
                self.s32(save=True, value=value["Extra Data"])
                self.s32(save=True, value=value["Controller"])
                self.u16(save=True, value=value["Flags"])
                self.vec3(save=True, value=value["Translation"])
                self.matrix33(save=True, value=value["Rotation"])
                self.single(save=True, value=value["Scale"])
                self.vec3(save=True, value=value["Velocity"])
                self.u32(save=True, value=value["Num Properties"])
                self.s32(value["Num Properties"], save=True, value=value["Properties"])
                self.bool(save=True, value=value["Has Bounding Volume"])
                if value["Has Bounding Volume"]:
                    self.BoundingVolume(save=True, value=value["Bounding Volume"])
                self.u32(save=True, value=value["Num Children"])
                self.s32(value["Num Children"], save=True, value=value["Children"])
                self.u32(save=True, value=value["Num Effects"])
                self.s32(value["Num Effects"], save=True, value=value["Effects"])
                return
            block = {
                "Name" : self.string(),
                "Extra Data" : self.s32(),
                "Controller" : self.s32(),
                "Flags" : self.u16(),
                "Translation" : self.vec3(),
                "Rotation" : self.matrix33(),
                "Scale" : self.single(),
                "Velocity" : self.vec3()
            }
            block["Num Properties"] = self.u32()
            block["Properties"] = self.s32(block["Num Properties"])
            block["Has Bounding Volume"] = self.bool()
            if block["Has Bounding Volume"]:
                block["Bounding Volume"] = self.BoundingVolume()
            block["Num Children"] = self.u32()
            block["Children"] = self.s32(block["Num Children"])
            block["Num Effects"] = self.u32()
            block["Effects"] = self.s32(block["Num Effects"])
            return block

        def NiLookAtController(self, save=False, value=None):
            if save:
                self.s32(save=True, value=value["Next Controller"])
                self.u16(save=True, value=value["Flags"])
                self.single(save=True, value=value["Frequency"])
                self.single(save=True, value=value["Phase"])
                self.single(save=True, value=value["Start Time"])
                self.single(save=True, value=value["Stop Time"])
                self.s32(save=True, value=value["Target"])
                self.s32(save=True, value=value["Look At"])
                return
            return {
                "Next Controller" : self.s32(),
                "Flags" : self.u16(),
                "Frequency" : self.single(),
                "Phase" : self.single(),
                "Start Time" : self.single(),
                "Stop Time" : self.single(),
                "Target" : self.s32(),
                "Look At" : self.s32()
            }

        def NiUVController(self, save=False, value=None):
            if save:
                self.s32(save=True, value=value["Next Controller"])
                self.u16(save=True, value=value["Flags"])
                self.single(save=True, value=value["Frequency"])
                self.single(save=True, value=value["Phase"])
                self.single(save=True, value=value["Start Time"])
                self.single(save=True, value=value["Stop Time"])
                self.s32(save=True, value=value["Target"])
                self.u16(save=True, value=value["Texture Set"])
                self.s32(save=True, value=value["Data"])
                return
            block = {
                "Next Controller" : self.s32(),
                "Flags" : self.u16(),
                "Frequency" : self.single(),
                "Phase" : self.single(),
                "Start Time" : self.single(),
                "Stop Time" : self.single(),
                "Target" : self.s32(),
                "Texture Set" : self.u16(),
                "Data" : self.s32()
            }
            return block
            
            pass
           
        def NiUVData(self, save=False, value=None):
            if save:
                self.KeyGroup(self.single, 4, save=True, value=value["UV Groups"])
                return
            block = {
                "UV Groups" : self.KeyGroup(self.single, 4)
            }
            return block
            
        def NiSequenceStreamHelper(self, save=False, value=None):
            if save:
                self.string(save=True, value=value["Name"])
                self.s32(save=True, value=value["Extra Data"])
                self.s32(save=True, value=value["Controller"])
                return
            return {
                "Name" : self.string(),
                "Extra Data" : self.s32(),
                "Controller" : self.s32()
            }

        def NiKeyframeData(self, save=False, value=None):
            if save:
                self.u32(save=True,value=value["Num Rotation Keys"])
                if value["Num Rotation Keys"] != 0:
                    self.u32(save=True,value=value["Rotation Type"])
                if value.get("Rotation Type", 0) != 4:
                    self.QuaternionKey(n=value["Num Rotation Keys"], arg=value.get("Rotation Type", 0), save=True,value=value["Quaternion Keys"])
                else:
                    if NetImmerseFileParser.validateVersion(self.data["header"]["Version"], until=[10,1,0,0]):
                        self.single(save=True,value=value["Order"])
                    self.KeyGroup(self.single, n=3, save=True,value=value["XYZ Rotations"])
                self.KeyGroup(self.vec3, save=True,value=value["Translations"])
                self.KeyGroup(self.KeyGroup, save=True,value=value["Scales"])
                return
            d = {
                "Num Rotation Keys" : self.u32()
            }
            if d["Num Rotation Keys"] != 0:
                d["Rotation Type"] = self.u32()
            if d.get("Rotation Type", 0) != 4:
                d["Quaternion Keys"] = self.QuaternionKey(d["Num Rotation Keys"], d.get("Rotation Type", 0))
            else:
                if NetImmerseFileParser.validateVersion(self.data["header"]["Version"], until=[10,1,0,0]): 
                    d["Order"] = self.single()
                d["XYZ Rotations"] = self.KeyGroup(self.single, 3)
            d["Translations"] = self.KeyGroup(self.vec3)
            d["Scales"] = self.KeyGroup(self.single)

            return d

        def NiTextKeyExtraData(self, save=False, value=None):
            if save:
                self.s32(save=True, value=value["Next Extra Data"])
                self.extraDataString(save=True, value=value["Extra Data"])
                self.u32(save=True, value=value["Num Text Keys"])
                self.Key(self.string, n=value["Num Text Keys"], arg=1, save=True, value=value["Text keys"])
                return
            data = {
                "Next Extra Data" : self.s32(),
                "Extra Data" : self.extraDataString(),
                "Num Text Keys" : self.u32()
            }
            data["Text keys"] = self.Key(self.string, n=data["Num Text Keys"], arg=1)
            return data
            pass
        
        def NiFlipController(self, save=False, value=None):
            if save:
                self.s32(save=True, value=value["Next Controller"])
                self.u16(save=True, value=value["Flags" ])
                self.single(save=True, value=value["Frequency" ])
                self.single(save=True, value=value["Phase" ])
                self.single(save=True, value=value["Start Time"])
                self.single(save=True, value=value["Stop Time"])
                self.s32(save=True, value=value["Target" ])
                self.u32(save=True, value=value["Texture Slot"])
                self.single(save=True, value=value["Accum Time"])
                self.single(save=True, value=value["Delta" ])
                self.u32(save=True, value=value["Num Sources"])
                self.s32(save=True, n=value["Num Sources"], value=value["Sources"])
                return
            block = {
                "Next Controller" : self.s32(),
                "Flags" : self.u16(),
                "Frequency" : self.single(),
                "Phase" : self.single(),
                "Start Time" : self.single(),
                "Stop Time" : self.single(),
                "Target" : self.s32(),
                "Texture Slot" : self.u32(),
                "Accum Time" : self.single(),
                "Delta" : self.single(),
                "Num Sources" : self.u32()
            }
            block["Sources"] = self.s32(block["Num Sources"])
            return block
        
        def NiGravity(self, save=False, value=None):
            if save:
                self.s32(save=True, value=value["Next Modifier"])
                self.s32(save=True, value=value["Controller"])
                self.single(save=True, value=value["Decay"])
                self.single(save=True, value=value["Force"])
                self.u32(save=True, value=value["Type"])
                self.vec3(save=True, value=value["Position"])
                self.vec3(save=True, value=value["Direction"])
                return
            return {
                "Next Modifier" : self.s32(),
                "Controller" : self.s32(),
                "Decay" : self.single(),
                "Force" : self.single(),
                "Type" : self.u32(),
                "Position" : self.vec3(),
                "Direction" : self.vec3()
            }
        
        def NiParticleRotation(self, save=False, value=None):
            if save:
                self.s32(save=True, value=value["Next Modifier"])
                self.s32(save=True, value=value["Controller"])
                self.u8(save=True, value=value["Random initial Axis"])
                self.vec3(save=True, value=value["Initial Axis"])
                self.single(save=True, value=value["Rotation Speed"])
                return
            return {
                "Next Modifier" : self.s32(),
                "Controller" : self.s32(),
                "Random initial Axis" : self.u8(),
                "Initial Axis" : self.vec3(),
                "Rotation Speed" : self.single()
            }
        
        def NiParticleGrowFade(self, save=False, value=None):
            if save:
                self.s32(save=True, value=value["Next Modifier"])
                self.s32(save=True, value=value["Controller"])
                self.single(save=True, value=value["Grow"])
                self.single(save=True, value=value["Fade"])
                return
            return {
                "Next Modifier" : self.s32(),
                "Controller" : self.s32(),
                "Grow" : self.single(),
                "Fade" : self.single(),
            }
            pass
                
        def NiParticleSystemController(self, save=False, value=None):
            if save:
                return
            block = {
                "Next Controller" : self.s32(),
                "Flags" : self.u16(),
                "Frequency" : self.single(),
                "Phase" : self.single(),
                "Start Time" : self.single(),
                "Stop Time" : self.single(),
                "Target" : self.s32(),
                "Speed" : self.single(),
                "Speed Variation" : self.single(),
                "Declination" : self.single(),
                "Declination Variation" : self.single(),
                "Planar Angle" : self.single(),
                "Planar Angle Variation" : self.single(),
                "Initial Normal" : self.vec3(),
                "Initial Color" : self.vec4(),
                "Initial Size" : self.single(),
                "Emit Start Time" : self.single(),
                "Emit Stop Time" : self.single(),
                "Reset Particle System" : self.u8(),
                "Birth Rate" : self.single(),
                "Lifetime" : self.single(),
                "Lifetime Variation" : self.single(),
                "Use Birth Rate" : self.u8(),
                "Spawn On Death" : self.u8(),
                "Emitter Dimensions" : self.vec3(),
                "Emitter" : self.s32(),
                "Num Spawn Generations" : self.u16(),
                "Percentage Spawned" : self.single(),
                "Spawn Multiplier" : self.u16(),
                "Spawn Speed Chaos" : self.single(),
                "Spawn Dir Chaos" : self.single(),
                "Num Particles" : self.u16(),
                "Num Valid" : self.u16()
            }
                
            block["Particles"] = self.NiParticleInfo(block["Num Particles"])
            block["Emitter Modifier"] = self.s32()
            block["Particle Modifier"] = self.s32()
            block["Particle Collider"] = self.s32()
            return block
            pass
        
        def NiAutoNormalParticlesData(self, save=False, value=None):
            if save:
                self.u16(save=True, value=value["Num Vertices"])
                self.bool(save=True, value=value["Has Vertices"])
                if value["Has Vertices"]:
                    self.vec3(value["Num Vertices"], True, value["Vertices"])
                self.bool(save=True, value=value["Has Normals"])
                if value["Has Normals"]:
                    self.vec3(value["Num Vertices"], True, value["Normals"])
                self.vec3(save=True, value=value["Bounding Sphere"]["Center"])
                self.single(save=True, value=value["Bounding Sphere"]["Radius"])
                self.bool(save=True, value=value["Has Vertex Colors"])
                if value["Has Vertex Colors"]:
                    self.vec4(value["Num Vertices"], True, value["Vertex Colors"])
                self.u16(save=True, value=value["Data Flags"])
                self.bool(save=True, value=value["Has UV"])
                if value["Has UV"]:
                    for i in range(value["Data Flags"] & 63):
                        self.vec2(value["Num Vertices"], True, value["UV Sets"][i])
                self.u16(save=True, value=value["Num Particles"])
                self.single(save=True, value=value["Particle Radius"])
                self.u16(save=True, value=value["Num Active"])
                self.bool(save=True, value=value["Has Sizes"])
                if block["Has Sizes"]:
                    self.single(save=True, n=value["Num Vertices"], value=value["Sizes"])
                # Needs "Has Rotation Angles" for check, doesnt exist in block and is not an arg
                return
            block = {
                "Num Vertices" : self.u16(),
                "Has Vertices" : self.bool()
            }
            if block["Has Vertices"] == True:
                block["Vertices"] = self.vec3(block["Num Vertices"])

            block["Has Normals"] = self.bool()
            if block["Has Normals"] == True:
                block["Normals"] = self.vec3(block["Num Vertices"])

            block["Bounding Sphere"] = {
                "Center" : self.vec3(),
                "Radius" : self.single()
            }

            block["Has Vertex Colors"] = self.bool()
            if block["Has Vertex Colors"] == True:
                block["Vertex Colors"] = self.vec4(block["Num Vertices"])
            block["Data Flags"] = self.u16()
            block["Has UV"] = self.bool()
            if block["Has UV"] == True:
                block["UV Sets"] = []
                for i in range(block["Data Flags"] & 63):
                    block["UV Sets"].append(self.vec2(block["Num Vertices"]))
            block["Num Particles"] = self.u16()
            block["Particle Radius"] = self.single()
            block["Num Active"] = self.u16()
            block["Has Sizes"] = self.bool()
            if block["Has Sizes"]:
                block["Sizes"] = self.single(block["Num Vertices"])
            # Needs "Has Rotation Angles" for check, doesnt exist in block and is not an arg
            return block

        def NiAutoNormalParticles(self, save=False, value=None):
            if save:
                self.string(save=True, value=value["Name"])
                self.s32(save=True, value=value["Extra Data"])
                self.s32(save=True, value=value["Controller"])
                self.u16(save=True, value=value["Flags"])
                self.vec3(save=True, value=value["Translation"])
                self.matrix33(save=True, value=value["Rotation"])
                self.single(save=True, value=value["Scale"])
                self.vec3(save=True, value=value["Velocity"])
                self.u32(save=True, value=value["Num Properties"])
                self.s32(value["Num Properties"], save=True, value=value["Properties"])
                self.bool(save=True, value=value["Has Bounding Volume"])
                if value["Has Bounding Volume"]:
                    self.BoundingVolume(save=True, value=value["Bounding Volume"])
                self.s32(save=True, value=value["Data"])
                self.s32(save=True, value=value["Skin Instance"])
                return
            block = {
                "Name" : self.string(),
                "Extra Data" : self.s32(),
                "Controller" : self.s32(),
                "Flags" : self.u16(),
                "Translation" : self.vec3(),
                "Rotation" : self.matrix33(),
                "Scale" : self.single(),
                "Velocity" : self.vec3(),
                "Num Properties" : self.u32(),
                "Properties" : []
            }
            block["Properties"] = self.s32(block["Num Properties"])
            block["Has Bounding Volume"] = self.bool()
            if block["Has Bounding Volume"] == True:
                block["Bounding Volume"] = self.BoundingVolume()
            block["Data"] = self.s32()
            block["Skin Instance"] = self.s32()

            return block
        
        def NiAlphaController(self, save=False, value=None):
            if save:
                self.s32(save=True, value=value["Next Controller"]),
                self.u16(save=True, value=value["Flags"]),
                self.single(save=True, value=value["Frequency"]),
                self.single(save=True, value=value["Phase"]),
                self.single(save=True, value=value["Start Time"]),
                self.single(save=True, value=value["Stop Time"]),
                self.s32(save=True, value=value["Target"]),
                self.s32(save=True, value=value["Data"])
                return
            return {
                "Next Controller" : self.s32(),
                "Flags" : self.u16(),
                "Frequency" : self.single(),
                "Phase" : self.single(),
                "Start Time" : self.single(),
                "Stop Time" : self.single(),
                "Target" : self.s32(),
                "Data" : self.s32()
            }
        
        def NiFloatData(self, save=False, value=None):
            if save:
                self.KeyGroup(self.single, save=True, value=value["Data"])
                return
            return {
                "Data" : self.KeyGroup(self.single)
            }
            
        def NiPosData(self, save=False, value=None):
            if save:
                self.KeyGroup(self.vec3, save=True, value=value["Data"])
                return
            return {
                "Data" : self.KeyGroup(self.vec3)
            }
        
        def NiCollisionSwitch(self, save=False, value=None):
            if save:
                self.string(save=True, value=value["Name"])
                self.s32(save=True, value=value["Extra Data"])
                self.s32(save=True, value=value["Controller"])
                self.u16(save=True, value=value["Flags"])
                self.vec3(save=True, value=value["Translation"])
                self.matrix33(save=True, value=value["Rotation"])
                self.single(save=True, value=value["Scale"])
                self.vec3(save=True, value=value["Velocity"])
                self.u32(save=True, value=value["Num Properties"])
                self.s32(value["Num Properties"], save=True, value=value["Properties"])
                self.bool(save=True, value=value["Has Bounding Volume"])
                if value["Has Bounding Volume"]:
                    self.BoundingVolume(save=True, value=value["Bounding Volume"])
                self.u32(save=True, value=value["Num Children"])
                self.s32(value["Num Children"], save=True, value=value["Children"])
                self.u32(save=True, value=value["Num Effects"])
                self.s32(value["Num Effects"], save=True, value=value["Effects"])
                return
            block = { 
                "Name" : self.string(),
                "Extra Data" : self.s32(),
                "Controller" : self.s32(),
                "Flags" : self.u16(),
                "Translation" : self.vec3(),
                "Rotation" : self.matrix33(),
                "Scale" : self.single(),
                "Velocity" : self.vec3(),
                "Num Properties" : self.u32()
            }
            block["Properties"] = self.s32(block["Num Properties"])
            block["Has Bounding Volume"] = self.bool()
            if block["Has Bounding Volume"] == True:
                block["Bounding Volume"] = self.BoundingVolume()
            block["Num Children"] = self.u32()
            block["Children"] = self.s32(block["Num Children"])
            block["Num Effects"] = self.u32()
            block["Effects"] = self.s32(block["Num Effects"])
            return block
        
        def NiPathController(self, save=False, value=None):
            if save:
                self.s32(save=save, value=value["Next Controller"])
                self.u16(save=save, value=value["Flags"])
                self.single(save=save, value=value["Frequency"])
                self.single(save=save, value=value["Phase"])
                self.single(save=save, value=value["Start Time"])
                self.single(save=save, value=value["Stop Time"])
                self.s32(save=save, value=value["Target"])
                self.u32(save=save, value=value["Bank Dir"])
                self.single(save=save, value=value["Max Bank Angle"])
                self.single(save=save, value=value["Smoothing"])
                self.u16(save=save, value=value["Follow Axis"])
                self.s32(save=save, value=value["Path Data"])
                self.s32(save=save, value=value["Percent Data"])
                return
            block = {
                "Next Controller" : self.s32(),
                "Flags" : self.u16(),
                "Frequency" : self.single(),
                "Phase" : self.single(),
                "Start Time" : self.single(),
                "Stop Time" : self.single(),
                "Target" : self.s32(),
                "Bank Dir" : self.u32(),
                "Max Bank Angle" : self.single(),
                "Smoothing" : self.single(),
                "Follow Axis" : self.u16(),
                "Path Data" : self.s32(),
                "Percent Data" : self.s32(),
            }
            return block
        
        def NiExtraData(self, save=False, value=None):
            if save:
                self.s32(save=True, value=value["Next Extra Data"]),
                self.byteArray(save=True, value=value["Extra Data"])
                return
            block = {
                "Next Extra Data" : self.s32(),
                "Extra Data"      : self.byteArray()
            }
            return block
        
        def NiParticlesData(self, save=False, value=None):
            if save:
                self.u16(save=True, value=value["Num Vertices"])
                self.bool(save=True, value=value["Has Vertices"])
                if value["Has Vertices"]:
                    self.vec3(value["Num Vertices"], True, value["Vertices"])
                self.bool(save=True, value=value["Has Normals"])
                if value["Has Normals"]:
                    self.vec3(value["Num Vertices"], True, value["Normals"])
                self.vec3(save=True, value=value["Bounding Sphere"]["Center"])
                self.single(save=True, value=value["Bounding Sphere"]["Radius"])
                self.bool(save=True, value=value["Has Vertex Colors"])
                if value["Has Vertex Colors"]:
                    self.vec4(value["Num Vertices"], True, value["Vertex Colors"])
                self.u16(save=True, value=value["Data Flags"])
                self.bool(save=True, value=value["Has UV"])
                if value["Has UV"]:
                    for i in range(value["Data Flags"] & 63):
                        self.vec2(value["Num Vertices"], True, value["UV Sets"][i])
                self.u16(save=True, value=value["Num Particles"])
                self.single(save=True, value=value["Particle Radius"])
                self.u16(save=True, value=value["Num Active"])
                self.bool(save=True, value=value["Has Sizes"])
                if value["Has Sizes"] == True:
                    self.bool(value["Num Vertices"], True, value=value["Sizes"])

                return
            block = {
                "Num Vertices" : self.u16(),
                "Has Vertices" : self.bool()
            }
            if block["Has Vertices"] == True:
                block["Vertices"] = self.vec3(block["Num Vertices"])
            block["Has Normals"] = self.bool()
            if block["Has Normals"] == True:
                block["Normals"] = self.vec3(block["Num Vertices"])
            block["Bounding Sphere"] = {
                "Center" : self.vec3(),
                "Radius" : self.single()
                }
            block["Has Vertex Colors"] = self.bool()
            if block["Has Vertex Colors"] == True:
                block["Vertex Colors"] = self.vec4(block["Num Vertices"])
            block["Data Flags"] = self.u16()
            block["Has UV"] = self.bool()
            if block["Has UV"] == True:
                block["UV Sets"] = []
                for i in range(block["Data Flags"] & 63):
                    block["UV Sets"].append(self.vec2(block["Num Vertices"]))      
            block["Num Particles"] = self.u16()
            block["Particle Radius"] = self.single()
            block["Num Active"] = self.u16()
            block["Has Sizes"] = self.bool()
            if block["Has Sizes"] == True:
                block["Sizes"] = self.single(block["Num Vertices"])
            # Needs "Has Rotation Angles" for check, doesnt exist in block and is not an arg
            
            return block
          
    class parser(NiBlocks):
        def load(self, filepath):
            return self.runner(filepath, True)
            
            #self.file = open(filepath, 'rb')
            #print(f"Reading {filepath.split('/')[:-1]}")
            #print("Parsing Header")
            #self.data["header"] = self.header()
            #self.data["Block List"] = []
            #print("Parsing Blocks")
            #for i in range(self.data["header"]["Num Blocks"]):
            #    # self.string length
            #    print(f"                             ", end='\r')
            #    print(f"Block: {i}", end='\r')
            #    block = {}
            #    block["Block Type"] = self.string()
            #    try:
            #        name = str(block["Block Type"][1])[2:-1]
            #        test = getattr(self, name, None)
            #        block["block"] = test()
            #        self.data["Block List"].append(block)
            #        
            #    except Exception as e:
            #        print(traceback.format_exc())
            #        print(f"Read Location: {self.file.tell()} Block {block['Block Type'][1]}")
            #        return None
            #print(f"                               ", end='\r')
            #print(f"Successfuly parsed all blocks.")
            #print(f"Parsing Footer")
            #self.data["footer"] = self.footer()
            #self.file.close()
            #print(f"Finished Reading {filepath.split('/')[:-1]}")
            #return self.data
            #pass
        
        def save(self, filepath):
            self.runner(filepath, False)
            pass
        
        def runner(self, filepath, load):
            self.file = open(filepath, 'rb' if load else 'wb')
            print(f"{'Reading' if load else 'Writing'}  {filepath.split('/')[-1]}")
            print(f"{'Parsing' if load else 'Writing'} Header")
            if load:
                self.data["header"] = self.header()
                self.data["Block List"] = []
            else:
                self.header(save=True, value=self.data["header"])
            
            print(f"{'Parsing' if load else 'Writing'} Blocks")
            for i in range(self.data["header"]["Num Blocks"]):
                # self.string length
                print(f"                             ", end='\r')
                print(f"Block: {i}", end='\r')
                if load:
                    block = {}
                    block["Block Type"] = self.string()
                else:
                    block = self.data["Block List"][i]
                    self.string(save=True, value=block["Block Type"])
                name = str(block["Block Type"][1])[2:-1]
                print(name)
                try:
                    test = getattr(self, name, None)
                    if load:
                        b = test()
                        if b == None:
                            pass
                        block["block"] = b
                        self.data["Block List"].append(block)
                    else:
                        test(save=True, value=block["block"])
                    
                except Exception as e:
                    print(e.traceback.format_exc())
                    if load:
                        print(f"Read Location: {self.file.tell()} Block {block['Block Type'][1]}")
                    else:
                        print(f"Block {block['Block Type'][1]}")
                    return None


            print(f"                               ", end='\r')
            print(f"Successfuly {'parsed' if load else 'written'} all blocks.")
            print(f"{'Parsing' if load else 'Writing'} Footer")
            if load:
                self.data["footer"] = self.footer()
            else:
                self.footer(save=True, value=self.data["footer"])
            self.file.close()
            print(f"Finished {'Reading' if load else 'Writing'} {filepath.split('/')[-1]}")
            if load: return self.data
            return
        
        def justBlocks(self, filepath, load):
            self.file = open(filepath, 'rb' if load else 'wb')
            size = os.path.getsize(filepath)
            if load:
                self.data["Block List"] = []
            i = 0
            while self.file.tell() < size:
                if load:
                    block = {}
                    try:
                        block["Block Type"] = self.string()
                    except:
                        print(traceback.format_exc())
                        print(f"Read Location: {self.file.tell()} Block {i} {block['Block Type'][1]}")
                        pass
                else:
                    block = self.data["Block List"][i]
                    self.string(save=True, value=block["Block Type"])
                try:
                    name = str(block["Block Type"][1])[2:-1]
                    test = getattr(self, name, None)
                    if test == None:
                        break
                    if load:
                        block["block"] = test()
                        self.data["Block List"].append(block)
                    else:
                        test(save=True, value=block["block"])
                except:
                    print(traceback.format_exc())
                    if load:
                        print(f"Read Location: {self.file.tell()} Block {i} {block['Block Type'][1]}")
                        pass
                    else:
                        pass
                    return None
                i += 1
                        #print(f"Block {block['Block Type'][1]}")
            with open("testoutput.json", 'w') as file:
                file.write(str(self.data["Block List"]))
        

        def ApplyTransformToShape(self, shape, transform):
            if not shape["Has Vertices"]: return
            scale = transform[0]
            rotate = transform[1]
            translate = transform[2]
            #print(shape["Vertices"][0])
            newverts = []
            for vert in shape["Vertices"]:
                nv = [x for x in vert]
                nv = ArrMath(nv, scale, "*")
                nv = matrix_rotate(rotate, nv)
                nv = ArrMath(nv, translate, "+")
                newverts.append(nv)
            shape["Vertices"] = newverts
            return shape
        
        def ArrayFix(self, nodeblock, Key, num_key):
            return [nodeblock[Key]] if nodeblock[num_key] == 1 else nodeblock[Key]
        
        def get(self, index):
            return self.data["Block List"][index]
        
        def getb(self, index):
            return self.get(index)["block"]
        
        def is_type(self, block, tpe):
            if type(tpe) is list:
                for t in tpe:
                    if block["Block Type"][1] == t: return True
                return False
            return block["Block Type"][1] == tpe
        
        def is_type_num(self, blocknum, tpe):
            return self.is_type(self.get(blocknum), tpe)
    
        def referencedbynode(self, index):
            res = []
            for i in range(len(self.data["Block List"])):
                NiNode = get(i)
                if not self.is_type(NiNode, b'NiNode'): continue
                children = self.ArrayFix(NiNode["block"], "Children", "Num Children")
                for child in children:
                    if child == index:
                        res.append(i)
                        break
        
        ## ============================================================= ##
        ## ============================================================= ##
        ## ============================================================= ##
        ## ============================================================= ##
        
        def Generate_OBJ_with_Shapes(self, filepath, shapes, output_filename, gamepath, output_folder, vertex_offset):
            self.data = {}
            print("Start Loading NIF - Generate_OBJ_with_Shapes")
            self.load(filepath)
            print("Finished Loading NIF - Generate_OBJ_with_Shapes")
            material_filename = f"{output_folder}/{output_filename}.mtl"
            object_filename = f"{output_folder}/{output_filename}.obj"
            res = f"mtllib {material_filename}"
            shapes = self.findTriShapeNodes_WithRoots(b"*COLLIDE", res=[], filter_blocks=shapes)
            print("Got Shapes - Generate_OBJ_with_Shapes")
            matdata = self.generate_material_data(shapes, gamepath, output_folder)
            print("Got Matdata - Generate_OBJ_with_Shapes")
            shapes_materials = matdata[0]
            
            
            
            with open(material_filename, 'w') as file:
                file.write(matdata[1])
            print("Wrote Material File - Generate_OBJ_with_Shapes")
            usedData = [0,0,0]
            i = 0
            for shape, root in shapes:
                sdata = self.getb(shape["Data"])
                print(f"Generating Shape: {shape['Data']}\n - Generate_OBJ_with_Shapes")
            # Shape 1

                translationNodes = [self.get(x) for x in root]

                # re-center object
                for vert in sdata["Vertices"]:
                    vert[0] -= vertex_offset[0]
                    vert[1] -= vertex_offset[1]
                    vert[2] -= vertex_offset[2]

                for t in reversed(translationNodes): # Transforms are applied from the flower to the root (for the longest time i assumed it was from the root to the flower)
                    tblock = t["block"]
                    sdata = self.ApplyTransformToShape(sdata, [[tblock["Scale"],tblock["Scale"],tblock["Scale"]], tblock["Rotation"], tblock["Translation"]])
                print("about to call 'generate_mesh_data' - Generate_OBJ_with_Shapes")
                shapefile = self.generate_mesh_data(str(shape["Name"][1]), shapes_materials[i], sdata, [0,0,0])   
                #with open(f"{output_folder}/{output_filename}_{str(shape['Name'][1])[2:][:-1].split('*')[0]}.obj", "w") as file:
                #    file.write(shapefile)
                
                res += self.generate_mesh_data(str(shape["Name"][1])[2:][:-1], shapes_materials[i], sdata, usedData)   
                res += "\n"
                i+=1
            
            
            with open(object_filename, "w") as file:
                file.write(res)
            
        def Generate_OBJ(self, filepath, output_filename, gamepath, output_folder):
            self.data = {}
            self.load(filepath)
            material_filename = f"{output_folder}/{output_filename}.mtl"
            object_filename = f"{output_folder}/{output_filename}.obj"
            res = f"mtllib ./{output_filename}.mtl\n"
            
            shapes = self.findTriShapeNodes_WithRoots(b"*COLLIDE", res=[])
            
            matdata = self.generate_material_data(shapes, gamepath, output_folder)
            
            shapes_materials = matdata[0]
            
            with open(material_filename, 'w') as file:
                file.write(matdata[1])
            
            usedData = [0,0,0]
            i = 0
            for shape, root in shapes:
                sdata = self.getb(shape["Data"])
                print(f"Generating Shape: {shape['Data']}")
            # Shape 1
                translationNodes = [self.get(x) for x in root]

                for t in reversed(translationNodes): # Transforms are applied from the flower to the root (for the longest time i assumed it was from the root to the flower)
                    tblock = t["block"]
                    sdata = self.ApplyTransformToShape(sdata, [[tblock["Scale"],tblock["Scale"],tblock["Scale"]], tblock["Rotation"], tblock["Translation"]])
                    
                shapefile = self.generate_mesh_data(str(shape["Name"][1]), shapes_materials[i], sdata, [0,0,0])   
                #with open(f"{output_folder}/{output_filename}_{str(shape['Name'][1])[2:][:-1].split('*')[0]}.obj", "w") as file:
                #    file.write(shapefile)
                
                res += self.generate_mesh_data(str(shape["Name"][1])[2:][:-1], shapes_materials[i], sdata, usedData)   
                res += "\n"
                i+=1
            
            
            with open(object_filename, "w") as file:
                file.write(res)
            
            pass

        def findTriShapeNodes_WithRoots(self, reject_if_in_name = None, root = [ 0 ], res=[], filter_blocks=[]):
            block = self.get(root[-1])
            if self.is_type(block, b"NiTriShape"):
                if (not reject_if_in_name in block["block"]["Name"][1]) or root[-1] == 0:
                    if len(filter_blocks) == 0 or root[-1] in filter_blocks:
                        res.append((block["block"], root))
                else:
                    pass
            elif self.is_type(block, [b"NiNode", b'NiCollisionSwitch']):
                children = self.ArrayFix(block["block"], "Children", "Num Children")
                #if block["block"]["Num Children"] == 1: children = [block["block"]["Children"]]
                #else: children = block["block"]["Children"]
                for child in children:
                    nextroot = [x for x in root]
                    nextroot.append(child)
                    self.findTriShapeNodes_WithRoots(reject_if_in_name, nextroot, res, filter_blocks)
            return res
        
        def generate_material_data(self, shapes, gamepath, output_folder):
            filestring = ""
            reslist = []
            mats = {}
            backup_namelist = []
            shapeIndex = 0
            outof = len(shapes)
            print("entering shape,root from shapes loop - generate_material_data")
            for shape, root in shapes:
                print(f"\n\nShape [{shapeIndex}/{outof}]({round((shapeIndex/outof)*100.0, 2)}%)\n", shape, root, f"- generate_material_data")
                shapeIndex+=1
                texturing = None
                material = None
                extension = "dds"
                failcheck = False
                # find material and texturing
                print("finding material and texturing")
                print("root Tree: ", root)
                for nodeindex in reversed(root):
                    print("current nodeindex: ", nodeindex)
                    if texturing != None and material != None: break
                    node = self.getb(nodeindex)
                    props = self.ArrayFix(node, "Properties", "Num Properties")
                    for prop in props:
                        if self.is_type(self.get(prop), b'NiTexturingProperty'):
                            texturing = self.getb(prop)
                        if self.is_type(self.get(prop), b'NiMaterialProperty'):
                            material = self.getb(prop)
                        if texturing != None and material != None:  break

                if material == None:
                    print("Failed to find 'NiMaterialProperty'")
                    material = {
                        "Name" : "BlankHalfVis",
                        "Extra Data" : -1,
                        "Controller" : -1,
                        "Flags" : 1,
                        "Ambient Color" : [1.0,1.0,1.0],
                        "Diffuse Color" : [1.0,1.0,1.0],
                        "Specular Color" : [1.0,1.0,1.0],
                        "Emissive Color" : [0.0,0.0,0.0],
                        "Glossiness" : 10.0,
                        "Alpha" : 0.5
                        }
                    # instead of returning None which throws an exception we pass a blank material
                    #return None

                print("found Material and texturing")
                # build material
                outpath = ""
                if not texturing == None:
                    print("texturing Not None")
                    source = None
                    if texturing["Has Base Texture"] == 1:
                        source = self.getb(texturing["Base Texture"]["Source"])
                        print("has base texture - generate_material_data")
                        # determine if file exists
                        # if it does create a hardlink to it where the image would normaly be extracted os.link(src,dest)
                        # as to not change how we reference the file in the mtl

                        # if it doesnt then extract it and save it to disk

                        if source["Use External"] == 1:
                            print("Use External - generate_material_data")
                        # extrapolate file path from relative
                            fp = str(source["File Name"][1])[2:][:-1].replace('\\','/').replace('//','/')
                            if fp[:3] == "../":
                                fp = fp.replace('../', f"{gamepath}/")

                            fn = fp.split('/')[-1]
                            outpath = f"{output_folder}/{fn.replace(' ','_')}"
                            reslist.append((outpath.split('/')[-1].split('.')[0]))
                            if not os.path.exists(outpath):
                                os.link(fp, outpath) #HARDLINK to original texture

                        
                        elif source["Use Internal"] == 1:
                        # Extract the texture
                            print("Use Internal - generate_material_data")
                            print("About to extract image - generate_material_data")
                            ddsimage, extension = self.image_from_pixeldata(self.getb(source["Pixel Data"]), source["Format Prefs"]["Use Mipmaps"])
                            #Find name
                            name = ""
                            print("image extracted - generate_material_data")
                            ## Get or generate Name
                            while True:
                                # Check NiSourceTexture 
                                print("Finding/Generating name - generate_material_data")
                                name = str(source['Name'][1])[2:][:-1]
                                if not name == "": break
                                print("name not in sourcetex - generate_material_data")
                                # check NiTexturingProperty 
                                name = str(texturing['Name'][1])[2:][:-1]
                                if not name == "": break
                                print("name not it texturing - generate_material_data")
                                # check root[-1] or NiTriShape 
                                name = str(self.getb(root[-1])['Name'][1])[2:][:-1]
                                if not name == "": break
                                print("name not in NiTriShape - generate_material_data")
                                # Check root[-2] or NiNode 
                                name = str(self.getb(root[-2])['Name'][1])[2:][:-1]
                                if not name == "": break
                                print("name not in NiNode - generate_material_data")
                                # Check NiMaterialProperty
                                name = str(material['Name'][1])[2:][:-1]
                                print("name not in NiMaterialProperty - generate_material_data")
                                if not name == "": break
                                
                                # Worst case reached. Generate Name.
                                print("Worst case reached - generating name - generate_material_data")
                                name = ""
                                abc_0_to_9 = []
                                a = "a"
                                
                                for i in range(48, 58):
                                    abc_0_to_9 += chr(i)
                                
                                for i in range(97, 123):
                                    abc_0_to_9 += chr(i)
                                
                                for i in range(8):
                                    name += abc_0_to_9[random.randint(0, len(abc_0_to_9)-1)]
                                
                                
                                break
                                # If all else Failes generate a random abc1-9 value of length 8 and use that as the name
                            name = name.replace('\\','/').replace(' ','_').replace("*", "-")
                            ##
                            print(f"name: {name} - generate_material_data")
                            #name = str(source['Name'][1])[2:][:-1].replace('\\','/').replace(' ','_')
                            
                            existing_image_found = False
                            existing_image_path = None
                            if name == "":
                                name = str(shape["Name"][1])[2:][:-1].split("*")[0]
                                existing = len(glob.glob(f"{output_folder}/{name}_*.*"))
                                name += f"_{existing+1}"

                                # check if the images are the same
                                for f in glob.glob(f"{output_folder}/*.*"):
                                    f = f.replace('\\','/')
                                    with open(f, "rb") as file:
                                        efile = file.read()
                                        if efile == ddsimage:
                                            #existing_image_found = True
                                            #existing_image_path = f
                                            name = f.split('/')[-1].split('.')[0]
                                            break
                                #for n in backup_namelist:
                                #    with open(f"{output_folder}/{n}.dds", "rb") as file:
                                #        efile = file.read()
                                #        if efile == ddsimage:
                                #            existing_image_found = True
                                #            existing_image = n
                                #            break
                                #backup_namelist.append(name)

                            writepath = f"{output_folder}/{name.split('/')[-1].split('.')[0]}.{extension}"
                            outpath = f"./{name.split('/')[-1].split('.')[0]}.{extension}"
                            reslist.append(outpath.split('/')[-1].split('.')[0])
                            # Extra check at end to see if a file that is the same but witha a different name exists
                            print(f"checking to see if texture already exists - generate_material_data")
                            for f in glob.glob(f"{output_folder}/*.{extension}"):
                                with open(f, "rb") as file:
                                    efile = file.read()
                                    if efile == ddsimage:
                                        print(f"found mathcing texture (will use hardlink to existing) - generate_material_data")
                                        existing_image_found = True
                                        existing_image_path = f.replace('\\','/')
                                        break
                                        
                            if not os.path.exists(writepath):
                                if existing_image_found:
                                    print(f"writing hardlink to texture - generate_material_data")
                                    os.link(existing_image_path, writepath)
                                else:
                                    print(f"writing texture - generate_material_data")
                                    wf(writepath, ddsimage, True)   
                                    #with open(writepath, 'wb') as file:
                                    #    file.write(ddsimage)

                        # For some reason the Use External and use Internal were both 0, a clear error    
                        else: failcheck = True
                    # No base texture found
                    else: failcheck = True
                else: 
                    print("No Texture")
                    fname = None
                    for b in reversed(root):
                        bl = self.getb(b)
                        n = bl.get("Name",[0,b""])[1] 
                        if not n == b"":
                            fname = str(n)[2:][:-1]
                            break
                    if fname == None:
                        failcheck = True
                    else: 
                        outpath = f"./{fname}.{extension}"
                        reslist.append(fname)
                
                if failcheck:
                # fall back on blank texture
                    outpath = f"{output_folder}/blank.dds"
                    if not os.path.exists(outpath):
                        # create a blank dds file (made with gimp, stripped gimp signature) 1x1 pixel white
                        ddsimage = b"\x44\x44\x53\x20\x7C\x00\x00\x00\x07\x10\x08\x00\x01\x00\x00\x00\x01\x00\x00\x00\x08\x00\x00\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x5C\x09\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x20\x00\x00\x00\x04\x00\x00\x00\x44\x58\x54\x31\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xFF\xFF\xFF\xFF\xAA\xAA\xAA\xAA"
                        with open(outpath, 'wb') as file:
                            file.write(ddsimage)
                    reslist.append(outpath.split('/')[-1].split('.')[0])

                    
                
                
                matpath = "./" + outpath.split('/')[-1]
                matname = matpath.split('/')[-1].split('.')[0]
                if not matname in mats.keys():
                    Ka = material["Ambient Color"]
                    Kd = material["Diffuse Color"]
                    Ks = material["Specular Color"]
                    mats[matname] = f"newmtl {matname}\n"
                    mats[matname] += f"Ka {Ka[0]} {Ka[1]} {Ka[2]}\n"
                    mats[matname] += f"Kd {Kd[0]} {Kd[1]} {Kd[2]}\n"
                    mats[matname] += f"Ks {Ks[0]} {Ks[1]} {Ks[2]}\n"
                    mats[matname] += f"d {material['Alpha']}\n"
                    mats[matname] += f"map_d {matpath}\n"
                    mats[matname] += f"Ns {material['Glossiness']}\n"
                    mats[matname] += f"Ni 1\n"
                    if not texturing == None: mats[matname] += f"map_Kd {matpath}\n\n"
            
            print(mats, "- generate_material_data")
            for mat in mats.values():
                filestring += mat
                
            
            return (reslist, filestring)
        
        def generate_mesh_data(self, Name, MaterialName, NiTriShapeData, usedData):
            # used data exisst to offset the vericies indices in the obj file for each consecutive shape passed in or it will break
            # used data = [vert count, uv count, normal count]
            if not NiTriShapeData["Has Vertices"]: return None
            numvert = 0
            numuv = 0
            numnorm = 0
            
            result = "\n"
            result += f"g {Name}\n"
            result += f"usemtl {MaterialName}\n"
            
            verts = self.ArrayFix(NiTriShapeData, "Vertices", "Num Vertices")
            for vert in verts:
                result += f"v {round(vert[0], 3)} {round(vert[1],3)} {round(vert[2],3)}\n"
            numvert = len(verts)
            
            if NiTriShapeData["Has UV"]:
                for vt in NiTriShapeData["UV Sets"][0]:
                    result += f"vt {round(vt[0], 3)} {-round(vt[1],3)}\n"
            else:
                for v in range(numvert):
                    result += f"vt {0} {0}\n"
            numuv = numvert
            
            normals = None
            if NiTriShapeData["Has Normals"]:
                normals = self.ArrayFix(NiTriShapeData, "Normals", "Num Vertices")
                if not normals == False:
                    for vn in normals:
                        result += f"vn {round(vn[0],3)} {round(vn[1],3)} {round(vn[2],3)}\n"
                    numnorm = numvert
            
            faces = self.ArrayFix(NiTriShapeData, "Triangles", "Num Triangles")
            if not faces == False:
                for f in faces:
                    f_v = lambda xyz: f"{usedData[0]+f[xyz]+1}"
                    f_vt = lambda xyz: f"/{usedData[1]+f[xyz]+1}" if numuv > 0 else ""
                    f_vn = lambda xyz: f"/{usedData[2]+f[xyz]+1}" if numnorm > 0 else ""
                    result += f"f {f_v(0)}{f_vt(0)}{f_vn(0)} {f_v(1)}{f_vt(1)}{f_vn(1)} {f_v(2)}{f_vt(2)}{f_vn(2)}\n"
            usedData[0] += numvert
            usedData[1] += numuv
            usedData[2] += numnorm
            return result
        
        def Bitmap_from_PixelData(self, colordata, w, h, bytes_per_pixel):
            #bytes_per_pixel = 4
            # Split the color data into Chunks based on the Bytes per pixel count RGB: 3 RGBA : 4
            ColorChunks = self.split_array(colordata, bytes_per_pixel)
            print("color Chunks created - Bitmap_from_PixelData")
            #w = len(pd)//w
            #h = len(pd)//h
            # Prepare a 2D colordata grid ready for population
            colordata2D = [[ [] for _ in range(w)] for _ in range(h)] # RGBA
            print("colordata2D reserved - Bitmap_from_PixelData")

            # here pd seems to be an array of pixels and not the raw bytes
            # BGRA
            print("about to poulate colordata2D - Bitmap_from_PixelData")
            i = 0
            for y in range(h):
                if i >= len(ColorChunks): break
                for x in range(w):
                    if i >= len(ColorChunks): break
                    data = [
                        ColorChunks[i][2],
                        ColorChunks[i][1],
                        ColorChunks[i][0]
                    ]
                    if bytes_per_pixel == 4: data.append(ColorChunks[i][3])
                    
                    colordata2D[y][x].extend(data)
                    
                    i+=1
            print("colordata2D populated - Bitmap_from_PixelData")
            
            #for i in range(w * h):
            #    x = i % w
            #    y = i // w
            #    
            #    # the pixel
            #    data = [
            #        ColorChunks[i][2],
            #        ColorChunks[i][1],
            #        ColorChunks[i][0]
            #    ]
            #    if bytes_per_pixel == 4: data.append(ColorChunks[i][3])
            #    
            #    colordata2D[y][x].extend(data)
                
                
                #if len(pd[i]) == 4: data.append(pd[i])
                #else:
                #    data.append(255)
            print("fliping Y axis - Bitmap_from_PixelData")
            colordata2D.reverse()
            colorbytesbuffer = []
            print("pixelbytes: ", h*w*bytes_per_pixel, "pixels: ", h*w)
            
            for y in range(h):
                for x in range(w):
                    for b in range(bytes_per_pixel):
                        colorbytesbuffer.append(colordata2D[y][x][b])
                        #colorbytes += struct.pack('B', colordata2D[y][x][b])
            colorbytes = bytes(colorbytesbuffer) #struct.pack(f"{h*w*bytes_per_pixel}B", *colorbytesbuffer)
            
            print("building bitmap header - Bitmap_from_PixelData")
            # HEADER
            filedata = b''
            
            # BITMAP HEADER DEFINE
            bfType          = b'BM'
            bfSize          = 54 + (w * h * bytes_per_pixel)
            bfReserved1     = 0
            bfReserved2     = 0
            bfOffBits       = 54
            
            # DIB HEADER DEFINE
            biSize          = 40
            biWidth         = w
            biHeight        = h
            biPlanes        = 1
            biBitCount      = 8 * bytes_per_pixel
            biCompression   = 0
            biSizeImage     = w * h * bytes_per_pixel
            biXPelsPerMeter = 0
            biYPelsPerMeter = 0
            biClrUsed       = 0
            biClrImportant  = 0
            
            
            print("packing header to filedata - Bitmap_from_PixelData")
            # BITMAP HEADER PACK
            filedata        += bfType
            filedata        += struct.pack('I', bfSize)
            filedata        += struct.pack('H', bfReserved1)
            filedata        += struct.pack('H', bfReserved2)
            filedata        += struct.pack('I', bfOffBits)
            
            # DIB HEADER PACK
            filedata        += struct.pack('I', biSize)
            filedata        += struct.pack('I', biWidth)
            filedata        += struct.pack('I', biHeight)
            filedata        += struct.pack('H', biPlanes)
            filedata        += struct.pack('H', biBitCount)
            filedata        += struct.pack('I', biCompression)
            filedata        += struct.pack('I', biSizeImage)
            filedata        += struct.pack('I', biXPelsPerMeter)
            filedata        += struct.pack('I', biYPelsPerMeter)
            filedata        += struct.pack('I', biClrUsed)
            filedata        += struct.pack('I', biClrImportant)
            
            # Pixel Data
            print("appending color data to filedata - Bitmap_from_PixelData")
            filedata        += colorbytes
            
            return filedata

        def PixelData_from_Palette(self, NiPalette, index_list):
            result = []
            for x in index_list:
                result.extend(NiPalette["Palette"][x])
            return result
        
        def split_array(self, arr, chunk_size):
            return [arr[i:i + chunk_size] for i in range(0, len(arr), chunk_size)]
        
        def decompress_dxt1(self, pixeldata, bbp):
            pd_blocks = self.split_array(pixeldata, 8)
            new_pixeldata = []
            
            def unpack_565(color):
                r = ((color >> 11) & 0x1F) << 3
                g = ((color >> 5) & 0x3F) << 2
                b = (color & 0x1F) << 3
                return [r, g, b]
            
            def interpolate_colors(C0, C1):
                if C0 < C1:
                    C2 = [(2 * C0[0] + 1 * C1[0]) // 3, (2 * C0[1] + 1 * C1[1]) // 3, (2 * C0[2] + 1 * C1[2]) // 3]
                    C3 = [(1 * C0[0] + 2 * C1[0]) // 3, (1 * C0[1] + 2 * C1[1]) // 3, (1 * C0[2] + 2 * C1[2]) // 3]
                else:
                    C2 = [(C0[0] + C1[0]) // 2, (C0[1] + C1[1]) // 2, (C0[2] + C1[2]) // 2]
                    C3 = [0, 0, 0]
                return C2, C3
            
            
            
            def unpack_indices(index_block):
                indices = []
                for i in range(16):
                    index = (index_block >> (2 * i)) & 0x03
                    indices.append(index)
                return indices
            
            def decompress_block(colors:list, indices):
                block = []
                for i in range(16):
                    block.append(colors[indices[i]])
                return block
            
            def colorRGB565_to_colorRGBA8888(pixeldata):
                new_pixeldata = []
                for col in pixeldata:
                    r = col[0]
                    g = col[1]
                    b = col[2]
                    a = 255
                    new_pixeldata.append([r,g,b,a])
                return new_pixeldata
            
            pixeldata = []
            for pdb in pd_blocks:
                c0 = struct.unpack("H", bytes([pdb[0],pdb[1]]))[0]
                c1 = struct.unpack("H", bytes([pdb[2],pdb[3]]))[0]
                index_block = struct.unpack("I", bytes([pdb[4],pdb[5],pdb[6],pdb[7]]))[0]
                
                c0 = unpack_565(c0)
                c1 = unpack_565(c1)
                
                c2, c3 = interpolate_colors(c0, c1)
                
                indices = unpack_indices(index_block)
                
                decompressed_block = decompress_block([c0,c1,c2,c3], indices)
                pixeldata.extend(decompressed_block)
            return colorRGB565_to_colorRGBA8888(pixeldata)
        
        def ForceOpaqueOrTransparent(self, pd):
            # R G B A
            pixels = self.split_array(pd, 4)
            result = []
            for pixel in pixels:
                
                # if has color
                if pixel[0] > 0 or pixel[1] > 0 or pixel[0] > 0:
                    pixel[3] = 255
                # else if has transparency
                elif pixel[3] < 255:
                    result.extend([0,0,0,0])
                    continue
                # else probably black
                result.extend([
                    pixel[0],
                    pixel[1],
                    pixel[2],
                    pixel[3]
                ])
            return result
            
        def StripAlphaRGB(self, pd):
            # R G B A
            pixels = self.split_array(pd, 4)
            result = []
            for pixel in pixels:
                result.extend([
                    pixel[0],
                    pixel[1],
                    pixel[2]
                ])
            return result
                
        #  16/05/2025 
        def RGB16_bpP_to_RGB_24_32_bpP(self, NiPixelData):
            def countBits(number):
                if number == 0: return 0
                bitfield = 0
                count = 0
                countstarted = False
                while True:
                    if bitfield == 0: bitfield = 1
                    else: bitfield = bitfield << 1
                    res = number & bitfield
                    if res > 0:
                        countstarted = True
                        count+=1
                    else:
                        if countstarted:
                            break
                return count

            # Load the pixel data to a bytearray
            pixeldata = bytes(NiPixelData["Pixel Data"])
            

            Rmask = NiPixelData["Red Mask"]
            Gmask = NiPixelData["Green Mask"]
            Bmask = NiPixelData["Blue Mask"]
            Amask = NiPixelData["Alpha Mask"]


            bpP = NiPixelData["Bits Per Pixel"]

            Size = (NiPixelData["Mipmaps"][0]["Width"], NiPixelData["Mipmaps"][0]["Height"])

            pixelformat = "RGB" if NiPixelData["Pixel Format"] == 0 else "RGBA"

            Rbits = countBits(Rmask)
            Gbits = countBits(Gmask)
            Bbits = countBits(Bmask)
            Abits = countBits(Amask)

            print(f"Converting PixelData: R: {Rbits} G: {Gbits} B: {Bbits} A: {Abits}")

            masks = {
                "Green" : (Gmask, Gbits),
                "Alpha" : (Amask, Abits),
                "Blue"  : (Bmask, Bbits),
                "Red"   : (Rmask, Rbits),
            }

            masks = dict(sorted(masks.items(), key=lambda item: item[1][0], reverse=True))

            mm0 = pixeldata[0:(Size[0]*Size[1])*2]

            output = b""
            for i in range(0, len(mm0), 2):
                j = i + 1

                pixel = struct.unpack("H",struct.pack("BB",mm0[i],mm0[j]))[0]

                #print(bin(pixel))

                results = {}
                remainingbits = bpP
                if pixelformat == "RGB": # rgb565
                    for i in range(len(masks)):
                        Key = list(masks.keys())[i]
                        Value = masks[Key]
                        if Value[1] == 0: continue
                        
                        anded_fp = pixel & Value[0]
                        shiftamount = remainingbits - Value[1]
                        shiftedmask = Value[0] >> shiftamount
                        shifted = anded_fp >> shiftamount
                        
                        if shifted == 0: results[Key] = 0
                        else: results[Key] = round(shifted / shiftedmask * 255)
                        remainingbits -= Value[1]
                    output += struct.pack("BBB", results["Red"], results["Green"], results["Blue"])
                    
                elif "RGBA": # rgb4444
                    for i in range(len(masks)):
                        Key = list(masks.keys())[i]
                        Value = masks[Key]    
                        anded_fp = pixel & Value[0]
                        shiftamount = remainingbits - Value[1]
                        shifted = (anded_fp >> shiftamount) & 0b1111
                        color = (shifted << 4) | shifted
                        results[Key] = color
                        remainingbits -= 4
                    output += struct.pack("BBBB", results["Red"], results["Green"], results["Blue"], results["Alpha"])
            colorspacecount = 3 if pixelformat == "RGB" else 4
            #with open("D:/SteamLibrary/steamapps/common/Oddworld Munchs Oddysee/zore/MunchsOddyseeTagManager/markers/TESTOUT/generator.pixdat", "wb") as f:
            #    f.write(bytes(output))
            
            return list(output)#[0:Size[0]*Size[1]*colorspacecount]
        
        def image_from_pixeldata(self, pd, mipmaps):
            fm_dict = [
                "RGB", # 0
                "RGBA",# 1
                "PAL",# 2
                "PALA",# 3
                "DXT1",# 4
                "DXT3",# 5
                "DXT5",# 6
                "RGB24NONlNT",# 7
                "BUMP",# 8
                "BUMPLUMA",# 9
                "RENDERSPEC",# 10
                "ICH",# 11
                "2CH",# 12
                "3CH",# 13
                "4CH",# 14
                "DEPTH STENCIL",# 15
                "UNKNOWN"# 16
            ]
            
            # The first mipmap always exists as it is the base image before LODing
            mms = self.ArrayFix(pd, "Mipmaps", "Num Mipmaps")
            width = mms[0]["Width"]
            height = mms[0]["Height"]
            extension = "dds"
            frmat = pd["Pixel Format"]
            pdata = []
            match(frmat):
                case 0: # RGB
                    print("format RGB - image_from_pixeldata")
                    match(pd["Bytes Per Pixel"]):
                        case 4:
                            print("32bpP or 4BpP - image_from_pixeldata")
                            colordata = list(self.StripAlphaRGB(pd["Pixel Data"])) # RGB should not have 4 bytes of data
                            pdata = self.Bitmap_from_PixelData(colordata, width, height, 3)
                            return pdata, "bmp"                  
                        case 3:
                            print("24bpP or 3BpP - image_from_pixeldata")
                            colordata = pd["Pixel Data"]
                            pdata = self.Bitmap_from_PixelData(colordata, width, height, 3)
                            return pdata, "bmp"
                        case 2:
                            print("16bpP or 2BpP - image_from_pixeldata")
                            colordata = self.RGB16_bpP_to_RGB_24_32_bpP(pd)
                            pdata = self.Bitmap_from_PixelData(colordata, width, height, 3)
                            return pdata, "bmp"
                        
                case 1: # RGBA
                    print("format RGBA - image_from_pixeldata")
                    match(pd["Bytes Per Pixel"]):
                        case 4:
                            print("32bpP or 4BpP - image_from_pixeldata")
                            colordata = pd["Pixel Data"]
                            pdata = self.Bitmap_from_PixelData(colordata, width, height, 4)
                            return pdata, "bmp"  
                            #frmat = 0
                        case 2:
                            print("16bpP or 2BpP - image_from_pixeldata")
                            colordata = self.RGB16_bpP_to_RGB_24_32_bpP(pd)
                            pdata = self.Bitmap_from_PixelData(colordata, width, height, 4)
                            return pdata, "bmp"
                        
                case 2: # PAL
                    print("format PAL - image_from_pixeldata")
                    pdata = self.PixelData_from_Palette(self.getb(pd["Palette"]), pd["Pixel Data"][0:width*height*pd["Bytes Per Pixel"]])
                    pdata = self.Bitmap_from_PixelData(pdata, width, height, 4)
                    extension = "bmp"
                    return pdata, extension
                
                case 4 | 5: # DXT1, DXT3
                    print("format DXT1 or DXT3 - image_from_pixeldata")
                    pdata = pd["Pixel Data"]
                
                #case 0 | 1 | 4 | 5: # RGB, RGBA, DXT1, DXT3
                #    match(frmat):
                #        case 0: # RGB
                #            match(pd["Bytes Per Pixel"]):
                #                case 4:
                #                    pdata = self.StripAlphaRGB(pd["Pixel Data"])
                #                case 3:
                #                    pdata = pd["Pixel Data"]
                #                case 2:
                #                    
                #                    colordata = self.RGB16_bpP_to_RGB_24_32_bpP(pd)
                #                    pdata = self.Bitmap_from_PixelData(colordata, width, height, 3)
                #                    return pdata, "bmp"

                #                    pass
                #        case 1: # RGBA
                #            match(pd["Bytes Per Pixel"]):
                #                case 4:
                #                    pdata = self.StripAlphaRGB(pd["Pixel Data"])
                #                    frmat = 0
                #                case 2:
                #                    
                #                    colordata = self.RGB16_bpP_to_RGB_24_32_bpP(pd)
                #                    pdata = self.Bitmap_from_PixelData(colordata, width, height, 4)
                #                    return pdata, "bmp"

                        
                
                    # I was trying to convert dds dxt1 to bitmap but was having problems,
                    # so im keeping it as dds dxt1 for now

                    #if pd["Bits Per Pixel"] == 0:
                    #    # assume ofc1 is 4
                    #    pdata = self.decompress_dxt1(pd["Pixel Data"], pd["Old Fast Compare"][0])
                    #else: 
                    #    pdata = self.split_array(pd["Pixel Data"], 4)
                    #pdata = self.Bitmap_from_PixelData(pdata, width, height)
                    #extension = "bmp"
                    #return pdata, extension
            
                case _:
                    print(f"BITMAP Transform Unhandled for format {frmat} - {fm_dict[frmat]}")
                    raise "FAILED to parse image"
                
                
            
            # checks
            compressed = frmat in [4, 5, 6]
            hasMipMaps = mipmaps >= 1
            alphapixels = frmat == 1
            
            # DEFINING
            
            # MAGIC NUMBER
            header2 = b"DDS "
            # Size of structure. This member must be set to 124.
            hSize = 124
            
            # Flags to indicate which members contain valid data.

            HasDepth = False
            
            DDSD_CAPS = 0x1                                     # Required in every dds file.
            DDSD_HEIGHT = 0x2                                   # Required in every dds file.
            DDSD_WIDTH = 0x4                                    # Required in every dds file.
            DDSD_PITCH = 0x8 if not compressed else 0           # Required when pitch is provided for an uncompressed texture.
            DDSD_PIXELFORMAT = 0x1000                           # Required in every dds file.
            DDSD_MIPMAPCOUNT = 0x20000 if hasMipMaps else 0     # Required in a mipmapped texture.
            DDSD_LINEARSIZE = 0x80000 if compressed else 0      # Required when pitch is provided for a compressed texture.
            DDSD_DEPTH = 0x800000 if HasDepth else 0            # Required in a depth texture.
            
            hFlags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PITCH | DDSD_PIXELFORMAT | DDSD_MIPMAPCOUNT | DDSD_LINEARSIZE | DDSD_DEPTH
            #hFlags_1 = 1 << 0 | 1 << 1 | 1 << 2 | (0 if compressed else 1) << 3 
            #hFlags_2 = 1 << 4 
            #hFlags_3 = (1 if hasMipMaps else 0) << 1 | (1 if compressed else 0) << 3

            #hFlags_bytes = struct.pack("BBBB", hFlags_1, hFlags_2, hFlags_3, 0)
            #hFlags = struct.unpack("I", hFlags_bytes)[0]
            
            # Surface height (in pixels).
            hHeight = height
            
            # Surface width (in pixels).
            hWidth = width
            
            # For DXT3, this is the total number of bytes for the main image.
            hPitch = 0
            match(frmat):
                case 0: hPitch = width * 3
                case 1: hPitch = width * 4
                case 4: hPitch = int(width * height / 2)
                case 5: hPitch = len(pd["Pixel Data"])
                case 6: hPitch = width * height
            
            
            # Depth of a volume texture (in pixels), otherwise unused.
            hDepth = 0
            
            # Number of mipmap levels, otherwise unused.
            hMipMapCount = pd["Num Mipmaps"]
            
            # Reserved for future use.
            hReserved1 = b'\x00' * 44
            
            # DDS_PIXEL_FORMAT - A sub header within the header
           
            # Size of the structure. This member must be set to 32.
            pfSize = 32
            
            # Flags to indicate which members contain valid data.

            YUV_compressed = False
            OneChanColorUncomp  = False
            DDPF_ALPHAPIXELS    = 0x1       if alphapixels          else 0  # Texture contains alpha data; dwRGBAlphaBitMask contains valid data.
            DDPF_ALPHA          = 0x2       if alphapixels          else 0  # Used in some older DDS files for alpha channel only uncompressed data (dwRGBBitCount contains the alpha channel bitcount; dwABitMask contains valid data)
            DDPF_FOURCC         = 0x4       if compressed           else 0  # Texture contains compressed RGB data; dwFourCC contains valid data.
            DDPF_RGB            = 0x40      if not compressed       else 0  # Texture contains uncompressed RGB data; dwRGBBitCount and the RGB masks (dwRBitMask, dwGBitMask, dwBBitMask) contain valid data.
            DDPF_YUV            = 0x200     if YUV_compressed       else 0  # Used in some older DDS files for YUV uncompressed data (dwRGBBitCount contains the YUV bit count; dwRBitMask contains the Y mask, dwGBitMask contains the U mask, dwBBitMask contains the V mask)
            DDPF_LUMINANCE      = 0x20000   if OneChanColorUncomp   else 0  # Used in some older DDS files for single channel color uncompressed data (dwRGBBitCount contains the luminance channel bit count; dwRBitMask contains the channel mask). Can be combined with DDPF_ALPHAPIXELS for a two channel DDS file.
            
            pfFlags =  DDPF_ALPHAPIXELS | DDPF_ALPHA | DDPF_FOURCC | DDPF_RGB | DDPF_YUV | DDPF_LUMINANCE
            # Four character code for compressed formats.
            pfFourCC = 0
            match(frmat):
                case 4: pfFourCC = b'DXT1'
                case 5: pfFourCC = b'DXT3'
                case 6: pfFourCC = b'DXT5'
                case _: pfFourCC = b'\x00\x00\x00\x00' # 0
            
            # Number of bits in a pixel. Not used for compressed formats.
            pfRGBBitCount = 32
            match(frmat): 
                #case 0:
                #    if pd["Bytes Per Pixel"] == 3: pfRGBBitCount = 24 
                case 0 | 4:
                    pfRGBBitCount = 24
                case 1|5|6:
                    pfRGBBitCount = 32
                case _:
                    pfRGBBitCount = 32
            
            # Bit mask for the red, green, blue and alpha channels. 
            # Not used for compressed formats.
            pfRBitMask, pfGBitMask, pfBBitMask, pfABitMask = 0, 0, 0, 0
            if not compressed:
                pfRBitMask = pd["Red Mask"]
                pfGBitMask = pd["Green Mask"]
                pfBBitMask = pd["Blue Mask"]
                pfABitMask = pd["Alpha Mask"]
            
            # Additional Complexity about the surfaces stored.
            # Caps 1
            
            #hCaps_1 = (1 if hasMipMaps else 0) << 3
            #hCaps_2 = 1 << 4
            #hCaps_bytes = struct.pack("BBBB", hCaps_1, hCaps_2, 0, 0)
            
            #hCaps = struct.unpack("I", hCaps_bytes)[0]
            
            DDSCAPS_COMPLEX = 0x8 if hasMipMaps else 0
            DDSCAPS_TEXTURE = 0x1000
            DDSCAPS_MIPMAP = 0x400000 if hasMipMaps else 0
            
            hCaps = DDSCAPS_COMPLEX | DDSCAPS_MIPMAP | DDSCAPS_TEXTURE
            
            # Caps2
            hasCubeMaps = False
            hasVolumeTexture = False
            DDSCAPS2_CUBEMAP           = 0x200    if hasCubeMaps      else 0 # Required for a cube map.
            DDSCAPS2_CUBEMAP_POSITIVEX = 0x400    if DDSCAPS2_CUBEMAP else 0 # Required when these surfaces are stored in a cube map.
            DDSCAPS2_CUBEMAP_NEGATIVEX = 0x800    if DDSCAPS2_CUBEMAP else 0 # Required when these surfaces are stored in a cube map.
            DDSCAPS2_CUBEMAP_POSITIVEY = 0x1000   if DDSCAPS2_CUBEMAP else 0 # Required when these surfaces are stored in a cube map.
            DDSCAPS2_CUBEMAP_NEGATIVEY = 0x2000   if DDSCAPS2_CUBEMAP else 0 # Required when these surfaces are stored in a cube map.
            DDSCAPS2_CUBEMAP_POSITIVEZ = 0x4000   if DDSCAPS2_CUBEMAP else 0 # Required when these surfaces are stored in a cube map.
            DDSCAPS2_CUBEMAP_NEGATIVEZ = 0x8000   if DDSCAPS2_CUBEMAP else 0 # Required when these surfaces are stored in a cube map.
            DDSCAPS2_VOLUME            = 0x200000 if hasVolumeTexture else 0 # Required for a volume texture.
            
            hCaps2 = DDSCAPS2_CUBEMAP | DDSCAPS2_CUBEMAP_POSITIVEX | DDSCAPS2_CUBEMAP_NEGATIVEX | DDSCAPS2_CUBEMAP_POSITIVEY | DDSCAPS2_CUBEMAP_NEGATIVEY | DDSCAPS2_CUBEMAP_POSITIVEZ | DDSCAPS2_CUBEMAP_NEGATIVEZ | DDSCAPS2_VOLUME
            
            

            # Caps3 - Unused
            hCaps3 = 0
            
            # Caps4 - Unused
            hCaps4 = 0
            
            # Reserved2
            hReserved2 = 0
            
            # Reserved for future use.
            #hReserved2 = (1 if hasMipMaps else 0) << 6
            
            #header[pos] = hReserved2
            

            # PACKING
            header2 = b"DDS "
            header2 += struct.pack("I", hSize)
            header2 += struct.pack("<I", hFlags)
            header2 += struct.pack("<I", hHeight)
            header2 += struct.pack("<I", hWidth)
            header2 += struct.pack("<I", hPitch)
            header2 += struct.pack("I", hDepth)
            header2 += struct.pack("<I", hMipMapCount)
            header2 += hReserved1
            header2 += struct.pack("I", pfSize)
            header2 += struct.pack("I", pfFlags)
            header2 += pfFourCC
            header2 += struct.pack("<I", pfRGBBitCount)
            header2 += struct.pack("<I", pfRBitMask)
            header2 += struct.pack("<I", pfGBitMask)
            header2 += struct.pack("<I", pfBBitMask)
            header2 += struct.pack("<I", pfABitMask)
            header2 += struct.pack("<I", hCaps)
            header2 += struct.pack("<I", hCaps2)
            header2 += struct.pack("<I", hCaps3)
            header2 += struct.pack("<I", hCaps4)
            header2 += struct.pack("I", hReserved2)
            
            l2 = len(header2)
            header2 += b"\x00" * (128 - l2)
            
            wf("./header.pixeldata", header2, True)
            #test = bytes(header)
            pixeldata = header2
            pixeldata += bytes(pdata)
            return pixeldata, extension

        rgbashift = [0, 8, 16, 24]
        
## TESTING FUNCTIONS        

def LoadAndExportModel(srcNIF, outFolder, gameroot):
    srcNIF = srcNIF.replace('\\','/')
    filename = srcNIF.split('/')[-1].split('.')[0]
    print("==================================================================")
    if os.path.exists(f"{outFolder}/{filename}.obj"):
        print(filename, "already Exists, Skipping.")
        return
    print(f"Converting NIF: {srcNIF.split('/')[-1]}")
    print(f"Generating model: {filename} to: {outFolder}/{filename}.obj")
    parser = NetImmerseFileParser.parser()
    parser.Generate_OBJ(srcNIF, filename, gameroot, outFolder)

def LoadAllModelsFromGame(gameroot, outputroot, extractionset):
    # Create a list of srcs and dests
    modelList = []
    with open(extractionset, "r") as jsf:
        modelList.extend(json.loads(jsf.read()))
    print(modelList)
    # methods of object gen/extraction
    # ("EXTRACT", SRC_PATH) will extract the nif model to an obj using the path as a dest
    # ("FIND", DEST_PATH, SRC_LAYOUT_NIF, [NiTriShape_BLOCK_NUM]) 
    #   1 DEST_PATH - the file path excluding any exention as there will be multiple types
    #   2 SRC_LAYOUT_NIF - the path to the nif file that contains the blocks required
    #   3 - A list containing the shape and texture blocks required to extract
    
    # Find mode has a vertex offset parameter
    # this is a reference to the point which you want to be the origin of the shape your extracting
    # usually the bounding sphere is god enough, but if multiple shapes are involved then you may want to pick the 
    # average of them or try to position it somewhat central to all of them and at the bottom of the shapes
    
    #Export models and textures   
    i = 0 
    for model in modelList:
        print("ZORE LOG - ",model)    
        match(model[0]):
            case "EXTRACT":
                srcNIF = f"{gameroot}/{model[1]}"
                path = model[1].split('.')[0]
                outFolder = f"{outputroot}/{path}"
                if not os.path.exists(outFolder):
                    os.makedirs(outFolder)
                LoadAndExportModel(srcNIF, outFolder, gameroot)
            case "FIND":
                #outputPath = f"{outFolder}/{model[1]}"
                layoutNIF = f"{gameroot}/{model[2]}"
                filename = model[1].split('/')[-1]
                outFolder = f"{outputroot}/{model[1][0:-(len(filename)+1)]}"
                if not os.path.exists(outFolder):
                    os.makedirs(outFolder)
                print("==================================================================")
                if os.path.exists(f"{outFolder}/{filename}.obj"):
                    print(filename, "already Exists, Skipping.")
                    i += 1
                    continue
                print(f"Extracting from layout: {layoutNIF.split('/')[-1]}")
                print(f"Generating Model: {filename} to: {outFolder}/{filename}.obj")
                parser = NetImmerseFileParser.parser()
                parser.Generate_OBJ_with_Shapes(layoutNIF, model[3], filename, gameroot, outFolder, model[4])
            case "LINK":
                print("==================================================================")
                print("Linking obj from bundled assets")
                
                #filepath, shapes, output_filename, gamepath, output_folder
        i += 1
                
                
        
    print("==========================================================================================")
    
    print("Finished Exporting Fixing Textures (replace broken textures with correctly exported ones)")
    
    # 15/05/2025 - I have fixed the RGB/RGBA format 16bpP exporter and so the "broken" textures are no longer broken
    #              and so dont need replacing.
    
    # Replace broken textures
    replaceList = [
        #("LINK", "mechanics/mines/xcmet-00fmi01_bv/FloaterMine.dds", "mechanics/mines/xcmet-00tmi01_bv/FloaterMine.dds"),
        #("LINK", "mechanics/mines/xcmet-00fmi01_bv/red_ring.dds", "mechanics/mines/xcmet-00tmi01_bv/red_ring.dds"),
        #("FIND", "mechanics/door/nnmet-00doo01_bv/Cylinder11.dds", "layout/region00/room00/rg00rm00_bv.nif", 60),
        #("LINK", "mechanics/door/nnmet-00doo01_bv/Line09.dds", "mechanics/door/nnmet-00doo01_bv/Cylinder11.dds"),
        #("LINK", "mechanics/door/nnmet-00doo01_bv/Line10.dds", "mechanics/door/nnmet-00doo01_bv/Cylinder11.dds"),
        #("LINK", "mechanics/door/nnmet-00doo01_bv/Object01.dds", "mechanics/door/nnmet-00doo01_bv/Cylinder11.dds"),
        #("LINK", "mechanics/door/nnmet-00doo01_bv/Object02.dds", "mechanics/door/nnmet-00doo01_bv/Cylinder11.dds"),
        #("LINK", "mechanics/door/nnmet-00doo01_bv/Object03.dds", "mechanics/door/nnmet-00doo01_bv/Cylinder11.dds"),
        #("LINK", "mechanics/door/nnmet-00doo01_bv/Object05.dds", "mechanics/door/nnmet-00doo01_bv/Cylinder11.dds"),
        #("LINK", "mechanics/door/nnmet-00doo01_bv/Object08.dds", "mechanics/door/nnmet-00doo01_bv/Cylinder11.dds"),
        #("LINK", "mechanics/door/nnmet-00doo01_bv/Object09.dds", "mechanics/door/nnmet-00doo01_bv/Cylinder11.dds"),
    ]
    # Some textures may need to be grabbed from a level
    # The differernt things
    # ("COPY", DEST_PATH, SRC_PATH) (proably not needed due to link)
    # ("LINK", DEST_PATH, SRC_PATH) (Links the src image as the sedt image)
    # ("FIND", DEST_PATH, SRC_NIF_PATH, NiSourceTexture_BLOCK_NUM, NiPixelData_BLOCK_NUM) (extracts the specific st and pd from a nif file as the src)
    
    # Not Implimented 
    # ("MASK", DEST_PATH, SRC_IMAGE, MASK_IMAGE) (transparency mask to force transparency in an image)
    
    for replace in replaceList:
        print(replace)
        match(replace[0]):
            case "COPY":
                print(f"replacing {replace[1]} with {replace[2]}")
                with open(f"{outputroot}/{replace[2]}", "rb") as src:
                    with open(f"{outputroot}/{replace[1]}", "wb") as dst:
                        dst.write(src.read())
            case "LINK":
                
                print(f"replacing {replace[1]} with a hardlink to {replace[2]}")
                if os.path.exists(f"{outputroot}/{replace[1]}"):
                    os.remove(f"{outputroot}/{replace[1]}")
                os.link(f"{outputroot}/{replace[2]}",f"{outputroot}/{replace[1]}")
            case "FIND": # find in level, provide: level_path, NiSourceTexture Index, NIPixelData Index
                print(f"replacing {replace[1]} with texture {replace[2]}:{replace[3]}")
                parser = NetImmerseFileParser.parser()
                parser.load(f"{gameroot}/{replace[2]}")
                DoorST = parser.getb(replace[3])
                DoorPD = parser.getb(DoorST["Pixel Data"])
                tex, ext = parser.image_from_pixeldata(DoorPD, DoorST["Format Prefs"]["Use Mipmaps"])
                with open(f"{outputroot}/{replace[1]}", "wb") as f:
                    f.write(tex)
        
def CompareOriginalWithNew():#
    
    fp = NetImmerseFileParser.open_file_dialog()
    if fp == None: return
    data = None
    data = NetImmerseFileParser.parser()
    #if data == None: return
    if data.load(fp) == None: 
        return
    outfile = f"testoutput.{'nif' if '.nif' in str(fp) else 'kf'}"
    data.save(outfile)
    
def JustBlocks():
    fp = NetImmerseFileParser.open_file_dialog()
    if fp == None: return
    data = None
    data = NetImmerseFileParser.parser()
    #if data == None: return
    if data.justBlocks(fp, True) == None: 
        return
    #outfile = f"testoutput.{'nif' if '.nif' in str(fp) else 'kf'}"
    #data.save(outfile)
    pass
    
def to_json():
    fp = NetImmerseFileParser.open_file_dialog()
    if fp == None: return
    data = None
    data = NetImmerseFileParser.parser()
    #if data == None: return
    if data.load(fp) == None: 
        return
    with open("testoutput.json", "w") as file:
        file.write(str(data.data))

# read a mesh in blender and create a shapedata node from it
def to_objs():
    fp = NetImmerseFileParser.open_file_dialog()
    if fp == None: return
    parser = NetImmerseFileParser.parser()
    parser.Generate_OBJ(fp, "myfile", "D:/SteamLibrary/steamapps/common/Oddworld Munchs Oddysee", "D:/SteamLibrary/steamapps/common/Oddworld Munchs Oddysee/zore/MunchsOddyseeTagManager/markers")
    #parser.to_objs(fp, "myfile")
    
# MAIN ENTRY POINT

def load_in_level():
    parser = NetImmerseFileParser.parser()
    parser.load("D:/SteamLibrary/steamapps/common/Oddworld Munchs Oddysee/layout/region00/room00/rg00rm00_bv.nif")    
    
    DoorST = parser.getb(60)
    DoorPD = parser.getb(61)
    dds_tex = parser.image_from_pixeldata(DoorPD, DoorST["Format Prefs"]["Use Mipmaps"])
    
    pass

def export_all_textures(filename, output_folder):
    parser = NetImmerseFileParser.parser()
    parser.load(filename)
    pd_blocks = [] # (output name, block)
    for i in range(parser.data["header"]["Num Blocks"]):
        if parser.is_type_num(i, b'NiPixelData'):
            outputname = f"{filename.split('/')[-1]}[{i}]"
            pd_blocks.append((outputname, parser.getb(i)))
    
    for outName, PD in pd_blocks:
        pd, ext = parser.image_from_pixeldata(PD, 2)
        with open(f"{output_folder}/{outName}.{ext}", "wb") as file:
            file.write(pd)

def main():
    #export_all_textures("D:/SteamLibrary/steamapps/common/Oddworld Munchs Oddysee/layout/region00/room01/room01_bv_OG.nif", "D:/SteamLibrary/steamapps/common/Oddworld Munchs Oddysee/zore/MunchsOddyseeTagManager/texturedump")
    #load_in_level()
    LoadAllModelsFromGame(
        gameroot="D:/SteamLibrary/steamapps/common/Oddworld Munchs Oddysee", 
        outputroot="./markers2"
    )
    #LoadAndExportModel(
    #    srcNIF="D:/SteamLibrary/steamapps/common/Oddworld Munchs Oddysee/layout/region12/room13/room13_bv.nif",
    #    outFolder="./level_export",
    #    gameroot="D:/SteamLibrary/steamapps/common/Oddworld Munchs Oddysee")


if __name__ == "__main__":
    import tkinter
    from tkinter import filedialog
    import traceback
    main()
