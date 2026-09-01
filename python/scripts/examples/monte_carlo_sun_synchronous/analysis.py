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

# Load in our data
dfs = loadFilesMultiRun(filename="states.csv")

# Configure our doc
doc = AutoDocPy()
doc.title("Simple Monte Carlo Analysis")
doc.author("Alex Reynolds", "alex.reynolds@attxengineering.com")
doc.file("mc_analysis.adoc")

# Plot an overlay of our Monte Carlo trajectories on top of one another
x_sph, y_sph, z_sph = generateSphere(6378137.0, [0,0,0], 200)
pp = PlotPlotly(show_fig=False)
pp.x([list(df['sc_pos_0']) for df in dfs])
pp.y([list(df['sc_pos_1']) for df in dfs])
pp.z([list(df['sc_pos_2']) for df in dfs])
pp.title('Orbit Trajectory Monte Carlo')
pp.xlabel('X (m)')
pp.ylabel('Y (m)')
pp.zlabel('Z (m)')
pp()
fig = pp.figure()
fig.add_trace(go.Scatter3d(x=x_sph.flatten(), y=y_sph.flatten(), z=z_sph.flatten(), marker_color='blue'))
import plotly.io as pio
pio.renderers.default = "browser"
fig.show()

# Add plot to document twice -- once with extension and once without
doc.addPlotly(pp.figure(), "multi_run_orbits")

doc.closeDisplayDoc()