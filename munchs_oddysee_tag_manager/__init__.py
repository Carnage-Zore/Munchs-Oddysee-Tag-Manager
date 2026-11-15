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

bl_info = {
    "name": "Munch's Oddysee Tag Manager",
    "author": "CarnageZore",
    "version": (1, 0, 0),
    "blender": (5, 1, 1),
    "location": "3D View > Tools",
    "description": "A tag manager for munches oddysee's xin/xrg files.",
    "doc_url": "https://github.com/Carnage-Zore/Munchs-Oddysee-Tag-Manager",
    "category": "3D View",
    "license": "GPL"
}

import munchs_oddysee_tag_manager.manager as mo_tag_manager
import munchs_oddysee_tag_manager.LoadNif as loadnif
import importlib


def register():
    importlib.reload(mo_tag_manager)
    importlib.reload(loadnif)
    mo_tag_manager.register()

def unregister():
    mo_tag_manager.unregister()
    
if __name__ == "__main__":
    register()