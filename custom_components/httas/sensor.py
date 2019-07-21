import logging
import async_timeout
import asyncio
import aiohttp
import time
from homeassistant.helpers.aiohttp_client import async_get_clientsession

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.const import (CONF_PASSWORD, CONF_USERNAME,  CONF_FRIENDLY_NAME, CONF_IP_ADDRESS, DEVICE_CLASS_POWER, 
    CONF_SENSORS, CONF_SENSOR_TYPE, CONF_ICON, CONF_SCAN_INTERVAL)
from inspect import currentframe, getframeinfo
from homeassistant.const import  TEMP_CELSIUS, CONF_SCAN_INTERVAL

DOMAIN = 'httas'
ENTITY_ID_FORMAT = 'sensor.{}'
_LOGGER = logging.getLogger(__name__)


ASYNC_TIMEOUT = 5 # Timeout for async courutine

CONF_NOTIFICATION = 'notification'
CMND_STATUS = 'status%208'
CMND_POWER = 'POWER'
CMND_POWER_ON = 'Power%20On'
CMND_POWER_OFF = 'Power%20Off'

S_CMND = "CMND"
S_VALUE = "VALUE"
S_UNIT = "UNIT"
S_ICON = 'ICON'

ST_TEMPERATURE = 'temperature'
ST_CURRENT = 'current'
ST_VOLTAGE = 'voltage'
MAX_LOST = 5                        # Can be lost in commincation

# definition of type of sensors
SENSORS = {
    ST_TEMPERATURE :{ 
        S_CMND: CMND_STATUS,
        S_VALUE:  ["StatusSNS", "DS18B20","Temperature"] ,
        CONF_SCAN_INTERVAL: 30,
        S_UNIT:   TEMP_CELSIUS,
        S_ICON: ''
    },
    ST_VOLTAGE: {
        S_CMND: CMND_STATUS,
        S_VALUE:  ["StatusSNS","ENERGY", "Voltage"] ,
        CONF_SCAN_INTERVAL: 30,
        S_UNIT:   'V',
        S_ICON: ''
    }, 
    ST_CURRENT: {
        S_CMND: CMND_STATUS,
        S_VALUE:  ["StatusSNS", "ENERGY", "Current"] ,
        CONF_SCAN_INTERVAL: 5,
        S_UNIT: 'A',
        S_ICON: 'mdi:current-ac'
    }
}


# Validation of the user's configuration
SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_IP_ADDRESS): cv.string,    
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_NOTIFICATION, default = True): cv.boolean,
    vol.Required(CONF_SENSOR_TYPE): vol.In(SENSORS.keys())
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_USERNAME, default = ''): cv.string,    
    vol.Optional(CONF_PASSWORD, default = ''): cv.string,
    vol.Optional(CONF_ICON): cv.string,
    vol.Optional(CONF_SENSORS, default={}):
        cv.schema_with_slug_keys(SENSOR_SCHEMA),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the httas sensors."""
 
    # Assign configuration variables.
    # The configuration check takes care they are present.

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    sensors = config.get(CONF_SENSORS)
    
    entities = []
    for object_id, pars in sensors.items():        
        base_url = "http://{}/cm?".format(pars[CONF_IP_ADDRESS])
        # username and passord is using only when protected internal
        if len(username) > 0:
            base_url += '&user='+username
        if len(password) > 0:
            base_url += '&password='+password
        base_url += '&cmnd='    
        entity = SonoffSensor(hass, object_id, pars.get(CONF_FRIENDLY_NAME), pars.get(CONF_SENSOR_TYPE),  base_url, pars)
        entities.append(entity)
    add_entities(entities)

class SonoffSensor(Entity):
    """Representation of a Sonoff device sensor."""

    def __init__(self, hass, object_id, name, sensor_type, base_url, pars):        
        """Initialize the sensor."""
        self._name = name
        self.entity_id = ENTITY_ID_FORMAT.format(object_id+'_'+sensor_type)
        self._state = None        
        self._is_available = False
        self._sensor_type = sensor_type        
        self._base_url = base_url
        self._scan_interval = SENSORS[sensor_type][CONF_SCAN_INTERVAL]                
        self._unit_of_measurement = SENSORS[sensor_type][S_UNIT]
        self._cmnd = SENSORS[sensor_type][S_CMND]
        self._state = None
        icon = pars.get(CONF_ICON)        
        if icon is None:
            icon = SENSORS[sensor_type][S_ICON]
        self._icon = icon                
        self._next_expiration = None
        self._ip_address = pars[CONF_IP_ADDRESS]      
        self._notification = pars.get(CONF_NOTIFICATION)
        self._lost = 0
        self._lost_informed = False
        self._info_state_ok = True  # info that everything is ok
        
    def _debug(self, s):
        cf = currentframe()
        line = cf.f_back.f_lineno
        if s is None:
             s = ''
        _LOGGER.debug("line: {} ip_address: {} msg: {}".format(line, self._ip_address, s))

    @property
    def should_poll(self):
        """If entity should be polled."""
        # Has its own timer for refreshing
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon
        
    def _to_get(self, cmnd):
        return  self._base_url + cmnd        
    
    async def _do_update(self):
        self._debug("update: {}".format(self._cmnd))        
        
        websession = async_get_clientsession(self.hass)                
        value = None
        try:
            with async_timeout.timeout(ASYNC_TIMEOUT):            
                response = await websession.post(self._to_get(self._cmnd))                        
            if response is not None:
                try:                
                    value = await response.json()            
                except:            
                    value = None
        except:
            self._debug('except')
            
        self._debug("value: {}".format(value))                                             
            
        if value is None:
            self._state = None
            scan_interval = 5
            self._is_available = False
            if self._lost > MAX_LOST:
                scan_interval = 59
                self._lost = 0
                if not self._lost_informed:
                    if self._notification:
                        self.hass.components.persistent_notification.create(
                            "{} has permanent error.<br/>Please fix device. Scan interval is {} seconds now".format(self._ip_address, scan_interval),
                            title=DOMAIN)                
                    self._info_state_ok = False
                    self._lost_informed = True
            else:
                self._lost += 1
            self.async_schedule_update_ha_state()
            self._debug("no success scan interval reduced to {} seconds".format(scan_interval))
            self.hass.helpers.event.async_call_later(scan_interval, self._do_update())        
            return False
        self._lost = 0
        if not self._info_state_ok:
            if self._notification:
                self.hass.components.persistent_notification.create(
                    "{} is ok. Scan interval is {} seconds now".format(self._ip_address, self._scan_interval),
                    title=DOMAIN)      
            self._info_state_ok = True                                                     
        value = self._json_key_value(SENSORS[self._sensor_type][S_VALUE], value)                                            
        self._state = value
        self._is_available = True
        self.async_schedule_update_ha_state()
        self._debug("Next call in {} seconds".format(self._scan_interval))
        self.hass.helpers.event.async_call_later(self._scan_interval, self._do_update())        
        return True

    async def async_added_to_hass(self):        
        """Run when entity about to be added."""
        await super().async_added_to_hass()                
        await self._do_update()   
        self._debug("entity added")        
    
    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return True if entity is available."""
        return self._is_available

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement

    def _json_key_value(self, def_array, value):
        """ Mapping of returned values. Defined in httas_const.py """
        # Maybe can be done by Schema - no success how to do
        try:
            if value is None:
                return None        
            for key in def_array:
                if key in value.keys():
                    value = value[key]
                else :
                    return None
            return value
        except:        
            return None