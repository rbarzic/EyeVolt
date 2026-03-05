import machine
import time

ADC_PIN0 = 26
ADC_PIN1 = 27

mux0_eb = machine.Pin(13, machine.Pin.OUT)
mux0_eb.value(1)

mux0_S0 = machine.Pin(10, machine.Pin.OUT)
mux0_S1 = machine.Pin(11, machine.Pin.OUT)
mux0_S2 = machine.Pin(12, machine.Pin.OUT)

mux1_eb = machine.Pin(18, machine.Pin.OUT)
mux1_eb.value(1)

mux1_S0 = machine.Pin(21, machine.Pin.OUT)
mux1_S1 = machine.Pin(20, machine.Pin.OUT)
mux1_S2 = machine.Pin(19, machine.Pin.OUT)


def mux0(channel):
    b0 = bool(channel & 1)
    b1 = bool((channel & 2) >> 1)
    b2 = bool((channel & 4) >> 2)
    
    mux0_S0.value(b0)
    mux0_S1.value(b1)
    mux0_S2.value(b2)
    
    mux0_eb.value(0)

def mux1(channel):
    b0 = bool(channel & 1)
    b1 = bool((channel & 2) >> 1)
    b2 = bool((channel & 4) >> 2)
    
    mux1_S0.value(b0)
    mux1_S1.value(b1)
    mux1_S2.value(b2)
    
    mux1_eb.value(0)

def disable_mux0():
    mux0_eb.value(1)

def disable_mux1():
    mux1_eb.value(1)


try:
    adc0 = machine.ADC(ADC_PIN0)
    adc1 = machine.ADC(ADC_PIN1)
except Exception as e:
    print(f"Error initializing ADC: {e}")

print("-I- ADC initialized")

mux0(0)
mux1(0)

i = 0
voltage0 = [0,0,0,0,0,0,0,0]
voltage1 = [0,0,0,0]

while True:
    raw_value1 = adc1.read_u16()
    for j in range(0,8):
        mux0(j)
        time.sleep(0.01)
        raw_value0 = adc0.read_u16()
        voltage0[j] = raw_value0
    
    for j in range(0,4):
        mux1(j)
        time.sleep(0.01)
        raw_value1 = adc1.read_u16()
        voltage1[j] = raw_value1
    
    v = voltage0
    print(f"1::{v[0]:05} {v[1]:05} {v[2]:05} {v[3]:05} {v[4]:05} {v[5]:05} {v[6]:05} {v[7]:05}")
    v = voltage1
    print(f"2::{v[0]:05} {v[1]:05} {v[2]:05} {v[3]:05}")
    
    i = i + 1
