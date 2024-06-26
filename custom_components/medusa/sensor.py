"""Platform for sensor integration."""
import os
import re
import json
import logging
import requests
import voluptuous as vol
from datetime import datetime
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_PORT, CONF_TOKEN, CONF_HOST, CONF_PROTOCOL)

_LOGGER = logging.getLogger(__name__)
DEFAULT_NAME = "medusa"
DEFAULT_HOST = "localhost"
DEFAULT_PROTO = "http"
DEFAULT_PORT = "8081"
DEFAULT_SORTING = "name"
CONF_SORTING = "sort"
CONF_WEB_ROOT = "webroot"
DEFAULT_WEB_ROOT = ""

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PROTOCOL, default=DEFAULT_PROTO): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_SORTING, default=DEFAULT_SORTING): cv.string,
    vol.Optional(CONF_WEB_ROOT, default=DEFAULT_WEB_ROOT): cv.string
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    add_entities([MedusaSensor(config, hass)], True)


class MedusaSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, config, hass):
        self._state = None
        self._name = config.get(CONF_NAME)
        self.token = config.get(CONF_TOKEN)
        self.host = config.get(CONF_HOST)
        self.protocol = config.get(CONF_PROTOCOL)
        self.port = config.get(CONF_PORT)
        self.base_dir = str(hass.config.path()) + '/'
        self.data = None
        self.sort = config.get(CONF_SORTING)
        self.web_root = config.get(CONF_WEB_ROOT)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self.data

    def update(self):
        attributes = {}
        card_json = []
        card_shows = []
        init = {}
        """Initialized JSON Object"""
        init['title_default'] = '$title'
        init['line1_default'] = '$episode'
        init['line2_default'] = '$release'
        init['line3_default'] = '$number - $rating - $runtime'
        init['line4_default'] = '$genres'
        init['icon'] = 'mdi:eye-off'
        card_json.append(init)

        tv_shows = self.get_infos(self.protocol, self.host, self.port, self.web_root, self.token, 'schedule')

        directory = "{0}/www/custom-lovelace/{1}/images/".format(self.base_dir, self._name)
        if not os.path.exists(directory):
            os.makedirs(directory)
        regex_img = re.compile(r'\d+-(fanart|poster|banner)\.jpg')
        lst_images = list(filter(regex_img.search,
                                 os.listdir(directory)))
        del_images = list(filter(regex_img.search,
                                 os.listdir(directory)))  

        for category in tv_shows:
            for show in tv_shows.get(category):
                
                airdate_str = show["airdate"] + ' ' + show["airs"]
                airdate_dt = datetime.strptime(airdate_str, "%Y-%m-%d %A %I:%M %p")
                airdate = airdate_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                
                number = "S" + str(show["season"]).zfill(2) + "E" + str(show["episode"]).zfill(2)
                
                banner = "{0}-banner.jpg".format(show["showSlug"])
                fanart = "{0}-fanart.jpg".format(show["showSlug"])
                poster = "{0}-poster.jpg".format(show["showSlug"])
                
                card_items = {}
                card_items["airdate"] = airdate
                card_items["number"] = number
                card_items["category"] = category
                card_items["studio"] = show["network"]
                card_items["title"] = show["showName"]
                card_items["episode"] = show["epName"]
                card_items["release"] = show["airdate"]
                card_items["runtime"] = show["runtime"]
                card_items["poster"] = self.add_poster(lst_images, directory, poster, show["showSlug"], card_items, del_images)
                card_items["fanart"] = self.add_fanart(lst_images, directory, fanart, show["showSlug"], card_items, del_images)
                card_items["banner"] = self.add_banner(lst_images, directory, banner, show["showSlug"], card_items, del_images)                
                card_shows.append(card_items)

        if self.sort == "date":
            card_shows.sort(key=lambda x: x.get("airdate"))
        card_json = card_json + card_shows
        attributes["data"] = card_json
        self._state = "success"
        self.data = attributes
        self.delete_old_tvshows(del_images, directory)

    def get_infos(self, proto, host, port, web_root, token, cmd):
        url = "{0}://{1}:{2}{3}/api/v2/{5}/?category[]=soon&category[]=today&api_key={4}".format(
            proto, host, port, web_root, token, cmd)
        ifs_shows = requests.get(url).json()
        return ifs_shows

    def add_poster(self, lst_images, directory, poster, id, card_items, del_images):
        if poster in lst_images:
            if poster in del_images:
               del_images.remove(poster)

        else:
            img_data = requests.get("{0}://{1}:{2}{3}/api/v2/series/{5}/asset/posterThumb?api_key={4}".format(self.protocol, self.host, self.port, self.web_root, self.token, id))
            if not img_data.status_code.__eq__(200):
                _LOGGER.error(card_items)
                return ""

            try:
                open(directory + poster, 'wb').write(img_data.content)
            except IOError:
                _LOGGER.error("Unable to create file.")
        return "/local/custom-lovelace/{0}/images/{1}".format(self._name, poster)

    def add_fanart(self, lst_images, directory, fanart, id, card_items, del_images):
        if fanart in lst_images:
            if fanart in del_images:
               del_images.remove(fanart)
        else:
            img_data = requests.get("{0}://{1}:{2}{3}/api/v2/series/{5}/asset/fanart?api_key={4}".format(self.protocol, self.host, self.port, self.web_root, self.token, id))
            
            if not img_data.status_code.__eq__(200):
                return ""

            try:
                open(directory + fanart, 'wb').write(img_data.content)
            except IOError:
                _LOGGER.error("Unable to create file.")
        return "/local/custom-lovelace/{0}/images/{1}".format(self._name, fanart)

    def add_banner(self, lst_images, directory, banner, id, card_items, del_images):
        if banner in lst_images:
            if banner in del_images:
               del_images.remove(banner)
        else:
            img_data = requests.get("{0}://{1}:{2}{3}/api/v2/series/{5}/asset/banner?api_key={4}".format(self.protocol, self.host, self.port, self.web_root, self.token, id))
            _LOGGER.debug(img_data)
            if not img_data.status_code.__eq__(200):
                return ""

            try:
                open(directory + banner, 'wb').write(img_data.content)
            except IOError:
                _LOGGER.error("Unable to create file.")
        return "/local/custom-lovelace/{0}/images/{1}".format(self._name, banner)
        
    def delete_old_tvshows(self, del_images, directory):
        for img in del_images:
            try:
                os.remove(directory + img)
                _LOGGER.info("Delete finished tv show images")
            except IOError:
                _LOGGER.error("Unable to delete file.")
