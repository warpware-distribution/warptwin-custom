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
# written permission of ATTX, INC.
###############################################################################
"""
Analysis script for propulsion study

See description in script.py
"""
import pandas as pd
import plotly.graph_objects as go

from warptwinutils.AutoDocPy import AutoDocPy
from warptwinutils.PlotPlotly import PlotPlotly
from warptwinutils.analysisutils import generateSphere

# Import our data
df_sc = pd.read_csv('results/states.csv')

# Create document
doc = AutoDocPy()
doc.title("Propulsion System Analysis")
doc.author("Alex Reynolds", "alex.reynolds@attxengineering.com")
doc.file("prop_analysis.adoc")

# Plot the 3d trajectory of the spacecraft around Earth
doc.addPrimaryHeader("Spacecraft Inertial Position")
earth_traj = generateSphere(6378137.0, [0,0,0])
fig = go.Figure()
fig.add_trace(go.Scatter3d(x=earth_traj[0], y=earth_traj[1], z=earth_traj[2], mode='markers', marker=dict(color='blue'), name='Earth'))
fig.add_trace(go.Scatter3d(x=df_sc['pos_0'], y=df_sc['pos_1'], z=df_sc['pos_2'], mode='markers', name='Spacecraft'))
fig.show()
doc.addPlotly(fig)

# Plot the change in orbital elements against time
doc.addPrimaryHeader("Spacecraft Orbital Elements")

fig = go.Figure()
pp = PlotPlotly(x=df_sc['time'], y=[0.001*val for val in df_sc['a']], title='Semimajor Axis vs. Time', xlabel='Time (s)', ylabel='SMA (km)')
doc.addPlotly(pp.figure())

fig = go.Figure()
pp = PlotPlotly(x=df_sc['time'], y=[val for val in df_sc['e']], title='Eccentricity vs. Time', xlabel='Time (s)', ylabel='Eccentricity')
doc.addPlotly(pp.figure())

fig = go.Figure()
pp = PlotPlotly(x=df_sc['time'], y=[180/3.14159*val for val in df_sc['i']], title='Inclination vs. Time', xlabel='Time (s)', ylabel='Inclination (deg)')
doc.addPlotly(pp.figure())

# Plot the change in orbital elements against time
doc.addPrimaryHeader("Spacecraft Altitude")

fig = go.Figure()
pp = PlotPlotly(x=df_sc['time'], y=[0.001*val for val in df_sc['altitude_m']], title='Altitude vs. Time', xlabel='Time (s)', ylabel='Altitude (km)')
doc.addPlotly(pp.figure())

# Plot the change in orbital elements against time
doc.addPrimaryHeader("Spacecraft Mass")

fig = go.Figure()
pp = PlotPlotly(x=df_sc['time'], y=[val for val in df_sc['mass']], title='Mass vs. Time', xlabel='Time (s)', ylabel='Mass (kg)')
doc.addPlotly(pp.figure())

doc.closeDisplayDoc()