###############################################################################
# Copyright (c) ATTX INC 2026. All Rights Reserved.
#
# This software and associated documentation (the "Software") are the 
# proprietary and confidential information of ATTX INC. The Software is 
# furnished under a license agreement between ATTX and the user organization 
# and may be used or copied only in accordance with the terms of the agreement.
# Refer to 'license/attx_license.adoc' for standard license terms.
#
# EXPORT CONTROL NOTICE: THIS SOFTWARE MAY INCLUDE CONTENT CONTROLLED UNDER THE
# INTERNATIONAL TRAFFIC IN ARMS REGULATIONS (ITAR) OR THE EXPORT ADMINISTRATION 
# REGULATIONS (EAR99). No part of the Software may be used, reproduced, or 
# transmitted in any form or by any means, for any purpose, without the express 
# written permission of ATTX INC.
###############################################################################
#Simple Point Mass Gravity Spacecraft Tutorial
#----------------------------------
#This is an analysis code for the SImple Gravity
#Spacecraft Script that outputs two figures. The 
#position in each axis as a function of time 
#(plots overlaid), and a 3D graph of the position
#in X, Y, Z.

#Author: Alex Jackson

import pandas as pd
from warptwinutils.AutoDocPy import AutoDocPy
from warptwinutils.analysisutils import plotGoogleEarth, readH5Dataframe

# Import our data
df = readH5Dataframe('results/sc_states.h5')

# Create
doc = AutoDocPy()
doc.title("Simple Gravity Spacecraft Analysis")
doc.author("Alex Jackson", "alex.jackson@attxengineering.com")
doc.file("simple_gravity_spacecraft_analysis.adoc")

# Now generate a KML from our trajectory
lla_deg = [[],[],[]]
lla_deg[0] = [x*180/3.1415926 for x in df['latitude']]
lla_deg[1] = [x*180/3.1415926 for x in df['longitude']]
lla_deg[2] = list(df['altitude_m'])
plotGoogleEarth(lla_deg[0], lla_deg[1], lla_deg[2])