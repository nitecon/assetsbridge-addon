# Copyright (c) 2023, Nitecon Studios LLC.  All rights reserved.

# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####
import bpy
import os
import json


def read_bridge_file(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)


def write_bridge_file(obj, file_path):
    with open(file_path, 'w') as f:
        json.dump(obj, f, indent=4)


def recursively_create_directories(path):
    if not os.path.exists(path):
        os.makedirs(path)


def clean_path(path):
    return path.replace('\\', '/').replace('//', '/')


def get_object_export_path(ob_path):
    base_obj_path = get_asset_root()
    if base_obj_path.endswith('/'):
        base_obj_path = base_obj_path[:-1]
    if not ob_path.startswith('/'):
        ob_path = '/' + ob_path
    if not ob_path.endswith('/'):
        ob_path = ob_path + '/'
    return base_obj_path + ob_path


ADDON_NAME = "AssetsBridge"


def get_addon_preferences():
    """Returns the addon preferences, handling the addon name correctly."""
    return bpy.context.preferences.addons[ADDON_NAME].preferences


def get_asset_root():
    return clean_path(os.path.dirname(get_addon_preferences().filepaths[0].path))


def get_bridge_directory():
    """Returns the configured bridge directory path."""
    paths = get_addon_preferences().filepaths
    if paths and paths[0].path:
        return clean_path(os.path.dirname(paths[0].path))
    return ""


def get_from_unreal_path():
    """Returns the path for the from-unreal.json file (Unreal → Blender direction)."""
    bridge_dir = get_bridge_directory()
    if bridge_dir:
        return os.path.join(bridge_dir, "from-unreal.json")
    return ""


def get_from_blender_path():
    """Returns the path for the from-blender.json file (Blender → Unreal direction)."""
    bridge_dir = get_bridge_directory()
    if bridge_dir:
        return os.path.join(bridge_dir, "from-blender.json")
    return ""


def is_bridge_configured():
    """Checks if the bridge directory is properly configured."""
    paths = get_addon_preferences().filepaths
    if not paths or not paths[0].path:
        return False
    default_path = "//AssetsBridge.json"
    return paths[0].path != default_path and paths[0].path != ""
