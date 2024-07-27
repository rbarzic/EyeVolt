from machine import Pin,ADC
from time import sleep

led = Pin('LED', Pin.OUT)
print('Blinking LED Example')

adc0 = ADC(26)
adc1 = ADC(27)

mux0_eb = Pin('GPIO13', Pin.OUT)
mux0_S0 = Pin('GPIO10', Pin.OUT)
mux0_S1 = Pin('GPIO11', Pin.OUT)
mux0_S2 = Pin('GPIO12', Pin.OUT)

mux1_eb = Pin('GPIO18', Pin.OUT)
mux1_S0 = Pin('GPIO21', Pin.OUT)
mux1_S1 = Pin('GPIO20', Pin.OUT)
mux1_S2 = Pin('GPIO19', Pin.OUT)


def mux0 (channel):
  b0 = channel & 1
  b1 = (channel & 2)>>1
  b2 = (channel & 4)>>2
  
  mux0_S0.value(b0) 
  mux0_S1.value(b1)
  mux0_S2.value(b2)
  mux0_eb.value(0)

def mux1 (channel):
  b0 = channel & 1
  b1 = (channel & 2)>>1
  b2 = (channel & 4)>>2
  
  mux1_S0.value(b0) 
  mux1_S1.value(b1)
  mux1_S2.value(b2)
  mux1_eb.value(0)

mux0(4)
mux1(0) 

while True:
  led.value(not led.value())
  adc_data0 = adc0.read_u16()
  adc_data1 = adc1.read_u16()
  print(f"ADC0 {(adc_data0 / 65535)*3.3}")
  print(f"ADC1 {(adc_data1 / 65535)*3.3*0.5}")
  
  sleep(0.5)
