#!/usr/bin/env python3
import app as core
core.VERSION='10.0'
core.BG_VERSION='NOVA'
if __name__=='__main__':
    core.app.run(host='0.0.0.0',port=8080)
