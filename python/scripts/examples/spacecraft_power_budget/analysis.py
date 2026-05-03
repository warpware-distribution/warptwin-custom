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
"""
Monte Carlo Orbit Analysis
--------------------------
This script performs analysis on results from an n-run Monte
Carlo

Author: Alex Reynolds
"""
import os
import pandas as pd
from warptwinutils.AutoDocPy import AutoDocPy
import matplotlib.pylab as plt
from warptwinutils.analysisutils import loadFilesMultiRun, generateSphere
from warptwinutils.PlotPlotly import PlotPlotly
import plotly.graph_objects as go

# Load in our data from multiple runs
dfs = loadFilesMultiRun(filename="states.csv")

# Configure our doc
doc = AutoDocPy()
doc.title("Power Budget Analysis")
doc.author("Alex Reynolds", "alex.reynolds@attxengineering.com")
doc.file("power_analysis.adoc")

# First plot our orbit parameters
pp = PlotPlotly(show_fig=False)
pp.x([list(df['pos_0']) for df in dfs])
pp.y([list(df['pos_1']) for df in dfs])
pp.z([list(df['pos_2']) for df in dfs])
pp.title('Orbit Trajectory Visualization')
pp.xlabel('X (m)')
pp.ylabel('Y (m)')
pp.zlabel('Z (m)')
pp()

# Add plot to document twice -- once with extension and once without
doc.addPlotly(pp.figure(), "orbits")

# First plot our orbit parameters
pp = PlotPlotly(show_fig=False)
pp.x([list(df['time']) for df in dfs])
pp.y([list(df['battery_power_generation_in']) for df in dfs])
pp.title('Solar Panel Power Generation vs. Time')
pp.xlabel('Time (s)')
pp.ylabel('Power Generation (W)')
pp()

# Add plot to document twice -- once with extension and once without
doc.addPlotly(pp.figure(), "power_generation")

# Plot system power draw
pp = PlotPlotly(show_fig=False)
pp.x([list(df['time']) for df in dfs])
pp.y([list(df['battery_power_draw_out']) for df in dfs])
pp.title('System Power Draw vs. Time')
pp.xlabel('Time (s)')
pp.ylabel('Power Draw (W)')
pp()

# Add plot to document twice -- once with extension and once without
doc.addPlotly(pp.figure(), "power_draw")

# Plot voltage vs. time
pp = PlotPlotly(show_fig=False)
pp.x([list(df['time']) for df in dfs])
pp.y([list(df['battery_system_voltage']) for df in dfs])
pp.title('Battery Voltage vs. Time')
pp.xlabel('Time (s)')
pp.ylabel('Battery Voltage (V)')
pp()

# Add plot to document twice -- once with extension and once without
doc.addPlotly(pp.figure(), "voltage")

doc.closeDisplayDoc()