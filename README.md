# Httas

You can completely switch off MQTT on your Tasmota Sonoff device.
Communication is via web request officially published [here](https://github.com/arendst/Sonoff-Tasmota/wiki/Commands)

![Sonoff](https://github.com/JiriKursky/Custom_components/blob/master/library/sonoffbasic.jpg)

Installation: 
1. Via hacs just install
2. Change your *configuration.yaml*.


in *configuration.yaml* section *switches*
```yaml
- platform: httas
  switches:
    filtration:
      ip_address: xxx.xxx.x.xx # ip address sonnoff controlling filtration
      friendly_name: Filtration sonoff          
    subwoofer:
      friendly_name: Subwoofer
      ip_address: xxx.xxx.x.xx # ip address sonnoff controlling subwoofer        
```

You can put in configuration notification = false. In case when HA is not able reach device were will be no message. 


In case of sensors. Just now supporting DS18B20 for temperature and current.

Sensors
```yaml
- platform: httas
  sensors:
    filtration:      
      ip_address: xxx.xxx.x.xx 
      friendly_name: Temperature
      sensor_type: temperature    
    subwoofer:      
      ip_address: xxx.xxx.x.xx
      friendly_name: Subwoofer current      
      sensor_type: current                  
```
