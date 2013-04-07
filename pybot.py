#!/usr/bin/env python

import sys
import socket
import string
import select
import urllib2
import json
import time

class IRCClient:
	
	def __init__(self, host, port, nick, ident, realname):
		
		# Settings
		self._host = host
		self._port = port
		self._nick = nick
		self._ident = ident
		self._realname = realname
		
		# Receive buffer 
		self._recv = ''
		
		# Try to connect
		self._s = socket.socket()
		self._s.connect((self._host, self._port))
		
		self.send("NICK %s" % self._nick)
		self.send("USER %s %s bla :%s" % (self._ident, self._host, self._realname))
	
	def recv(self):
		
		while True:
			# Return full lines from the recv buffer
			i = self._recv.find("\r\n")
			if i >= 0:
				s = self._recv[:i]
				self._recv = self._recv[i + 2:]
				return s
			
			# Wait for more data from the server
			r = select.select([self._s], [], [], 0.250)
			if r[0]:
				self._recv += self._s.recv(4096)
			else:
				return False
	
	def send(self, message):
		
		self._s.send(message + "\r\n")
	
	def join(self, channel):
		
		self.send("JOIN :%s" % channel)
	
	def msg(self, target, message):
		
		print "%s: <%s> %s" % (target, self._nick, message)
		self.send("PRIVMSG %s :%s" % (target, message))
	
	def quit(self, message):
		
		self.send("QUIT :%s" % message)
		self._s.close()


class habitat:
	
	def __init__(self, url):
		
		self._url = url
		self._docs = []
		
		# Connect to server and get the sequence number
		r = self.fetch_doc('')
		
		self._db_name = r['db_name']
		self._update_seq = r['update_seq']
	
	def fetch_doc(self, document):
		
		j = urllib2.urlopen(self._url + document).read()
		j = json.loads(j)
		return j
	
	def fetch_updates(self):
		
		changes = self.fetch_doc("_changes?since=%i&include_docs=true" % self._update_seq)
		self._update_seq = changes['last_seq']
		
		r = False
		for change in changes['results']:
			if 'doc' in change:
				self._docs.append(change['doc'])
				r = True
		
		return r
	
	def read(self):
		
		if len(self._docs) == 0 and self.fetch_updates() == False:
			return False
		
		return self._docs.pop()
	
	def doc_type(self, doc):
		
		if doc == False: return False
		
		if 'type' in doc:
			return r['type']
		
		return False
	
	def doc_parsed(self, doc):
		
		if doc == False: return False
		
		if 'data' not in r: return False
		if '_parsed' not in r['data']: return False
		
		return True
	
	def doc_payload_id(self, doc):
		
		if self.doc_type(doc) != 'payload_telemetry':
			return False
		
		if self.doc_parsed(doc) != True:
			return False
		
		return doc['data']['_parsed']['payload_configuration']


payload = '14f4eb90052b267e43ade2d4bfbfafff'

hab = habitat('http://habitat.habhub.org/habitat/')

irc = IRCClient("irc.freenode.net", 6667, "mobybot", "mobybot", "mobybot")
irc.join("#sealevel")

# Current time
ts = time.time()

try:
	while True:
		# Every ten seconds, query habitat for updates
		if time.time() > ts + 10:
			
			ts = time.time()
			
			while True:
				r = hab.read()
				if r == False: break
				
				# Hacky
				if hab.doc_payload_id(r) == payload:
					
					alt = r['data']['altitude']
					lat = r['data']['latitude']
					lng = r['data']['longitude']
					int_temp = r['data']['temperature_internal']
					sentence = r['data']['sentence_id']
					
					irc.msg('#sealevel', 'New Position: %.05f, %.05f Altitude: %.02f Internal Temperature: %.02f' % (lat, lng, alt, int_temp))
					irc.msg('#sealevel', 'https://maps.google.co.uk/maps?q=%%40%.05f,%.05f&z=8' % (lat, lng))
		
		s = irc.recv()
		if s == False: continue
		
		if s[0] == ':':
			(source, s) = s[1:].split(None, 1)
			nick = source.split('!', 1)[0]
		else:
			source = False
			nick = False
		
		r = s.split(None, 1)
		
		if r[0] == "PING":
			irc.send("PONG %s" % r[1])
		
		elif r[0] == "JOIN":
			print "%s: * %s (%s) has joined" % (r[1], nick, source)
		
		elif r[0] == "QUIT":
			print "* %s has quit (Reason: %s)" % (nick, r[1][1:])
		
		elif r[0] == "PRIVMSG":
			r = r[1].split(None, 1)
			print "%s: <%s> %s" % (r[0], nick, r[1][1:])
		
		else:
			# Unknown message
			print "< %r" % s

except KeyboardInterrupt:
	print "Ctrl+C caught. Disconnecting"
	irc.quit("Glub glub glub....")

