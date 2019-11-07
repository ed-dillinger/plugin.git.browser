# -*- coding: utf-8 -*-

'''*
	This program is free software: you can redistribute it and/or modify
	it under the terms of the GNU General Public License as published by
	the Free Software Foundation, either version 3 of the License, or
	(at your option) any later version.

	This program is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	GNU General Public License for more details.

	You should have received a copy of the GNU General Public License
	along with this program.  If not, see <http://www.gnu.org/licenses/>.
*'''
import sys
import time
import xbmcgui
import requests
import shutil
import hashlib
import zipfile
from commoncore import kodi
from .github_api import get_version_by_name, get_version_by_xml, check_sha

if kodi.strings.PY2:
	from cStringIO import StringIO as functionIO
else:
	from io import BytesIO as functionIO

class downloaderException(Exception):
	pass

class hashException(Exception):
	pass

def hash_func(fname, algorithm="sha1"):
	try:
		hasher = getattr(hashlib, algorithm)()
		
	except hashException as e:
		raise hashException("Invalid hash algorithm")
	if fname.startswith("http"):
		r = requests.get(fname, stream=True)
		filesize = str(r.headers["Content-Length"])
		hasher.update(b"blob " + filesize + "\0")
		for chunk in r.iter_content(8096):
			hasher.update(chunk)
	else:
		hasher.update(b"blob " + str(kodi.vfs.get_size(fname)) + "\0")
		with open(fname, "rb") as f:
			for chunk in iter(lambda: f.read(8096), b""):
				hasher.update(chunk)
	return hasher.hexdigest()



def format_status(cached, total, speed):
	cached = kodi.format_size(cached)
	total = kodi.format_size(total)
	speed = kodi.format_size(speed, 'B/s')
	return	 "%s of %s at %s" % (cached, total, speed) 

def test_url(url):
	r = requests.head(url)
	return r.status_code == requests.codes.ok

def download(url, full_name, addon_id, destination, unzip=False, quiet=False, verify_hash=True):
	version = None
	filename = addon_id + '.zip'
	r = requests.get(url, stream=True)
	kodi.log("Download: %s" % url)

	if r.status_code == requests.codes.ok:
		temp_file = kodi.vfs.join(kodi.get_profile(), "downloads")
		if not kodi.vfs.exists(temp_file): kodi.vfs.mkdir(temp_file, recursive=True)
		temp_file = kodi.vfs.join(temp_file, filename)
		try:
			total_bytes = int(r.headers["Content-Length"])
		except:
			total_bytes = 0
		try:
			etag = r.headers["etag"][1:-1]
		except:
			etag = 0
		block_size = 1000
		cached_bytes = 0
		if not quiet:
			pb = xbmcgui.DialogProgress()
			pb.create("Downloading",filename,' ', ' ')
		kodi.sleep(150)
		start = time.time()
		is_64bit = sys.maxsize > 2**32
		with open(temp_file, 'wb') as f:
			for chunk in r.iter_content(chunk_size=block_size):
				if chunk:
					if not quiet and pb.iscanceled():
						raise downloaderException('Download Aborted')
						return False
					cached_bytes += len(chunk)
					shutil.copyfileobj(functionIO(chunk), f, 8096)
					if total_bytes > 0:
						delta = int(time.time() - start)
						if delta:
							bs = int(cached_bytes / (delta))
						else: bs = 0
						if not quiet:
							percent = int(cached_bytes * 100 / total_bytes)
							pb.update(percent, "Downloading",filename, format_status(cached_bytes, total_bytes, bs))
		
		if not quiet: pb.close()
		if verify_hash:
			local_sha = hash_func(temp_file, "sha1")
			if etag != local_sha:
				kodi.close_busy_dialog()
				kodi.handel_error('Download Error', "Checksum mismatch!")
		
		if unzip:
			if is_64bit:
				zip_ref = zipfile.ZipFile(temp_file, 'r')
			else:
				with open(temp_file, "rb") as zip_file:
					zip_ref = zip_file.ZipFile(functionIO(zip_file.read()))
			zip_ref.extractall(destination)
			zip_ref.close()
			kodi.vfs.rm(temp_file, quiet=True)
			try:
				xml = kodi.vfs.read_file(kodi.vfs.join(destination, kodi.vfs.join(addon_id, 'addon.xml')), soup=True)
				version = get_version_by_xml(xml)
				if not version:
					version = get_version_by_name(filename)
			except:
				kodi.log("Unable to fine version from addon.xml for addon: %s" % addon_id)
		else:
			kodi.vfs.mv(temp_file, kodi.vfs.join(destination, filename))
	else:
		kodi.close_busy_dialog()
		raise downloaderException(r.status_code)
	return version
	