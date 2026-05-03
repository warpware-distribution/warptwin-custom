""" =====================================================
The following python script is a derived class of the 
existing warpTwin Spacecraft class. This class is used 
to contain all the general information of your spacecraft 
model and act as a single source of sim truth. The prupose of
this example is to demonstrate the modularity and customizablity
that warpTwin provides for rapid analysis and devlopment of your
cubesat, rocket, etc. mission.

For the purpose of this example, we will demonstrate a feasablity
analysis and setup of a cubesat that must achieve the following.
Suppose your spacecraft has three mission modes: safe, nominal, 
and experiment. Based on your requirements and mission planning,
you believe that it would be best for safe mode to be tumbling
with as much hardware turned off as possible. Nominal mode should
have the antenna point nadir while secondarily prioritizing solar 
power generation. The experiment requires pointing a camera and
antenna (on same face) at the surface, so the same pointing as
nominal mode can be used.

The spacecraft body frame shall be defined consistently with the 
structures subsystem. The spacecrfat body frame is defined as such:
   +x -> [2U face] Nadir face, has antenna
   -x -> [2U face] Zenith face, has GPS receiver
   +y -> [3U face]
   -y -> [3U face]
   +z -> [6U face] Sun face, sun pointing in nominal mode
   -z -> [6U face] Shadow face, anti-sun pointing in nominal mode

Author James Tabony <james.tabony@attx.tech> : 10/31/25
===================================================== """

#########################################################
# Imports
#########################################################
# Spacecraft for tracking the spacecraft body and inheritence
from warptwin.Spacecraft import Spacecraft
# SpicePlanet for Earth data/configuration
from warptwin.SpicePlanet import SpicePlanet
# Common and neccessary WarpTwinPy imports
from warptwin.WarpTwinPy import (CartesianVector3, Quaternion, Matrix3, DEGREES_TO_RADIANS, connectSignals)
# IMU, Magnetometer, GPS and Sun sensor for sensor suite
from warptwin.SunSensor import SunSensor
# Solar panel and battery for power hardware suite
from warptwin.SolarPanelModel import SolarPanelModel
from warptwin.SimpleBatterySystem import SimpleBatterySystem
# Ground Station Model
from warptwin.GroundStationModel import GroundStationModel
# Frame State Sensor Model for necessary relative states
from warptwin.FrameStateSensorModel import FrameStateSensorModel

# os for file pathing
import os
# sys for code exiting
import sys
# Math for trig and sqrt functions
import math
# Numpy for matrix and vector operations
import numpy as np



class CustomSpacecraft(Spacecraft):
#########################################################
# Custom Class Constructor
#########################################################
    def __init__(self, exc):
        '''
        HOW TO USE THIS CLASS:
            # Import the CustomSpacecraft class
            from custom_spacecraft_analysis.CustomSpacecraft import CustomSpacecraft

            # Create an instance of the CustomSpacercaft class
            sc = CustomSpacercaft(exc)

            # Configure hardware using the configuration methods
            # Only sets some params, may need to do external configuration
            sc.config<hardware_name>FromJson(<Json_file_name>, <other_parameters>)

            # Now all configured hardware is accesable through the CustomSpacecraft instance
            # For example, to access the battery instance:
            battery = sc._battery
            # In general, hardware is stored in the instance variable
            <hardware_name> = sc._<hardware_name>
        '''
        # Initialize our self Spacecraft
        Spacecraft.__init__(self, exc, "CustomModel")
        # Define members of this class at initial configuration
        self._exc = exc

        # Config CustomSpacercaft to be around Earth
        self.earth = SpicePlanet(exc, "Earth")
        self.params.planet_ptr(self.earth)

        # Create a Sun model for sensor use
        self.sun = SpicePlanet(exc, "Sun")

        # Configure frame sensors
        self.__configure_frame_sensors__()

        # ***** Values would come from CAD model source of truth *****
        # Define mass of CustomSpacercaft [kg]
        self.params.mass(12.0)
        # Define mass moment of inertia of CustomSpacercaft [kg-m^2]
        self.params.inertia(Matrix3([[0.0333, 0.0012, 0.0005],[0.0012, 0.0837, 0.0016],[0.0005, 0.0016, 0.1037]]))



#########################################################
# CustomSpacecraft Frame Manager
#########################################################
    def __configure_frame_sensors__(self):
        '''
        NEVER USE THIS METHOD EXTERNALLY

        This method is automatically called in the CustomSpacecraft constructor.
        The purpose of this method is to initialize all the frame
        managers. I.e., giving direct access to the position of any object
        with respect to any object in any objects frame, when necessary.

        For this mission, all that is needed is the position of the earth and sun
        with respect to the CustomSpacecraft body, resolved in the earth inertial
        coordinates. This is for the two axis pointing guidance to determine the
        optimal attitude in nominal and experimental mission modes.
        '''
        # Create a frame sensor to retrieve nadir vector
        self.nadir_pointing_sensor = FrameStateSensorModel(self._exc, "CustomSpacecraft_nadir_pointing_sensor")
        self.nadir_pointing_sensor.params.target_frame_ptr(self.earth.outputs.inertial_frame())
        self.nadir_pointing_sensor.params.reference_frame_ptr(self.body())
        self.nadir_pointing_sensor.params.output_frame_ptr(self.earth.outputs.inertial_frame())

        # Create a frame sensor to retrieve sun vector
        self.sun_pointing_sensor = FrameStateSensorModel(self._exc, "CustomSpacecraft_sun_pointing_sensor")
        self.sun_pointing_sensor.params.target_frame_ptr(self.sun.outputs.inertial_frame())
        self.sun_pointing_sensor.params.reference_frame_ptr(self.body())
        self.sun_pointing_sensor.params.output_frame_ptr(self.earth.outputs.inertial_frame())



#########################################################
# CustomSpacecraft Set Initial State Method
#########################################################
    def initializeState(self, altitude, eccentricity, inclination, RAAN, argument_periapsis, mean_anomaly):
        '''
        The method is used to initialize the position, and velocity 
        of CustomSpacercaft. However, the prebuilt methods that
        comes with warpTwin's Spcaecraft class would also work.

        INPUTS
        altitude (float):
            The altitude of the semi-major axis of the orbit in meters
        eccentricity (float):
            The eccentricity of the orbit
        inclination (float):
            The inclination of the orbit in degrees
        RAAN (float):
            The right ascension of the ascending node of the orbit in degrees
        argument_periapsis (float):
            The argument of periapsis of the orbit in degrees
        mean_anomaly (float):
            The mean anomaly of the spacecraft within the orbit in degrees
        '''
        # Convert degrees to radians
        inclination         = inclination           * DEGREES_TO_RADIANS
        RAAN                = RAAN                  * DEGREES_TO_RADIANS
        argument_periapsis  = argument_periapsis    * DEGREES_TO_RADIANS
        mean_anomaly        = mean_anomaly          * DEGREES_TO_RADIANS

        # Find Eccentric Anomaly Using Newtons Method
        tolerance = 1e-15
        error = 1
        eccentric_anomaly = mean_anomaly
        while (error > tolerance):
            eccentric_anomaly = eccentric_anomaly - (eccentric_anomaly-eccentricity*math.sin(eccentric_anomaly)-mean_anomaly)/(1-eccentricity*math.cos(eccentric_anomaly))
            error = eccentric_anomaly-eccentricity*math.sin(eccentric_anomaly)-mean_anomaly
        
        # Find True Anomaly from Eccentric Anamoly
        true_anomaly = 2*math.atan(math.sqrt((1+eccentricity)/(1-eccentricity))*math.tan(eccentric_anomaly/2))

        # Finding position and velocity vectors in LVLH frame
        a = altitude+self.earth.outputs.eq_radius()         # Semi-major axis
        r = a*(1-eccentricity*math.cos(eccentric_anomaly))  # Radius
        h = math.sqrt(self.earth.outputs.mu()*a*(1-eccentricity*eccentricity))  # Specific angular momentum
        vr = self.earth.outputs.mu()*eccentricity*math.sin(true_anomaly)/h      # Radial component of velocity
        vt = h/r    # Theta-hat component of velocity
        position = np.array([r, 0.0, 0.0])
        velocity = np.array([vr, vt, 0.0])

        # Finding the 3-2-3 DCM for LVLH to ECI coordinate conversion
        theta = argument_periapsis + true_anomaly
        ROT1 = np.array([[math.cos(RAAN), -math.sin(RAAN), 0.0],
                        [math.sin(RAAN),  math.cos(RAAN), 0.0],
                        [     0.0,             0.0,       1.0]])    # Z-rotation by RAAN
        ROT2 = np.array([[1.0,        0.0,                    0.0           ],
                        [0.0, math.cos(inclination), -math.sin(inclination)],
                        [0.0, math.sin(inclination),  math.cos(inclination)]])  # X-rotation by inclination
        ROT3 = np.array([[math.cos(theta), -math.sin(theta), 0.0],
                        [math.sin(theta),  math.cos(theta), 0.0],
                        [      0.0,              0.0,       1.0]])  # Z-rotation by theta
        DCM = ROT1 @ ROT2 @ ROT3

        # Rotate the position and velocity vectors and set the spacecraft initial position and velocity
        position = CartesianVector3((DCM @ position).tolist())
        velocity = CartesianVector3((DCM @ velocity).tolist())
        self.initializePositionVelocity(position, velocity)



#########################################################
# CustomSpacecraft Fine Sun Sensor Configuration Method
#########################################################
    def configSunSensorFromJson(self, sun_sensor_name, rate, latency=0, sun_sensor_rng_seed=0):
        '''
        JSON files for the Sun Sensor are saved in the directory 
        './custom_sun_sensor_json'. Each JSON file corresponds 
        to a sun sensor that you may considering using.

        This method is where the alignment and position of the sun sensor
        within CustomSpacercaft is defined. Truth as defined from CAD model.

        INPUTS
        sun_sensor_name (string):
            Name of the sun sensor you wish to config CustomSpacercaft with, the name 
            should match the name of the JSON file and manufacturer provided name.
        rate (integer):
            Measurement rate of the sun sensor in Hz.
        latency (integer) [optional]:
            Latency of the sun sensor in milliseconds, default is 0.
        sun_sensor_rng_seed (integer) [optional]:
            Seed for the random number generator of the sun sensor,
            default is 0.
        '''
        # create the sun sensor and configure from the JSON file
        self.fine_sun_sensor = SunSensor(self._exc, "CustomSpacercaft_SUN_SENSOR")
        json_path = os.path.join(os.path.dirname(__file__), 'custom_sun_sensor_json', sun_sensor_name + '.json')
        error = self.fine_sun_sensor.configureFromJson(json_path)
        if error != 0:
            print("Error with fine sun sensor configure method! Check if input name is correct")
            sys.exit(1)

        # Set the rate of the Sun Sensor [Hz]
        self.fine_sun_sensor.params.rate_hz(rate)

        # Set the rng seed of the Sun Sensor
        self.fine_sun_sensor.params.seed_value(sun_sensor_rng_seed)

        # Set the latency of the sun sensor [ms]
        self.fine_sun_sensor.params.latency(latency)

        # Set initial noise characteristics assuming that there is no pointing bias
        self.fine_sun_sensor.params.pointing_bias(Quaternion({1.0, 0.0, 0.0, 0.0}))

        # Add Sun and Earth inertial frames
        self.fine_sun_sensor.params.sun_inertial_frame(self.sun.outputs.inertial_frame())
        self.fine_sun_sensor.params.primary_inertial_frame(self.earth.outputs.inertial_frame())

        # Add the Earth's radius
        self.fine_sun_sensor.params.primary_radius(self.earth.outputs.eq_radius())

        # ***** Values would come from CAD model source of truth *****
        ########## Mount the fine Sun sensor to the body frame of CustomSpacercaft ##########
        self.fine_sun_sensor.params.mount_frame(self.outputs.body())
        # Position of the fine Sun sensor frame wrt body frame resolved in body frame [m]
        self.fine_sun_sensor.params.mount_position__mf(CartesianVector3([0.0, 0.2, 0.0]))
        # Alignment of the sun sensor (rotation from mount frame to sensor frame)
        self.fine_sun_sensor.params.mount_alignment_mf(Quaternion({math.cos(math.pi/4), 0.0, -math.sin(math.pi/4), 0.0}))
        


#########################################################
# CustomSpacecraft Solar Panel Configuration Method
#########################################################
    def configSolarPanelFromJson(self, solar_panel_name, area_per_u=0.01):
        '''
        JSON files for the solar panels are saved in the directory
        './custom_solar_panel_json'. Each JSON file corresponds
        to a solar panel that you are considering using.

        The solar panels are acessable through
            self.panels[i] for i = [0, 1, 2, 3]
            # i = 0 -> +y face
            # i = 1 -> -y face
            # i = 2 -> +z face
            # i = 3 -> -z face

        INPUTS
        solar_panel_name (string):
            Name of the solar panel you wish to config CustomSpacecraft with, the name
            should match the name of the JSON file and manufacturer provided name.
            This name should be concatenated with _nU where n is the expected U
            of a given face (e.g., 2, 3, 6, etc.)
        area_per_u (float) [optional]:
            The aera of the solar panels in m^2 per U of surface area.
            This value cannot be greater than 0.01 m^2 and defaults to that value.
        '''
        # Define the order of body faces that solar panels are configured
        SOLAR_PANEL_FACE = ['posY',
                            'negY',
                            'posZ',
                            'negZ']
        # Define the orientations of the solar panels in body frame coordinates
        SOLAR_PANEL_NORMALS = [CartesianVector3([0.0,  1.0,  0.0]),  # +y -> 3U
                               CartesianVector3([0.0, -1.0,  0.0]),  # -y -> 3U
                               CartesianVector3([0.0,  0.0,  1.0]),  # +z -> 6U
                               CartesianVector3([0.0,  0.0, -1.0])]  # -z -> 6U
        # Define the size of each of the faces [U]
        FACE_SIZE_U = [3,
                       3,
                       6,
                       6]

        # Create the solar panels and configure it from the JSON file
        self.panels = []
        for i in range(len(SOLAR_PANEL_FACE)):
            # Create the next solar panel
            self.panels.append(SolarPanelModel(self._exc, "CustomSpacecraft_solar_panel_" + SOLAR_PANEL_FACE[i]))
            # Define the path to the JSON file
            json_path = os.path.join(os.path.dirname(__file__), 'custom_solar_panel_json', solar_panel_name + '_' + str(FACE_SIZE_U[i]) + 'U' +'.json')
            # Configure it from JSON
            error = self.panels[-1].configureFromJson(json_path)
            if  error != 0:
                print("Error with solar pannel configure method! Check if input name is correct")
                sys.exit(1)
            # Define the area
            self.panels[-1].params.panel_area(area_per_u * FACE_SIZE_U[i])
            # Define the orientation in body frame
            self.panels[-1].params.body_frame_ptr(self.outputs.body())
            self.panels[-1].params.panel_normal__body(SOLAR_PANEL_NORMALS[i])
            # Configure the sun and earth frames into the solar panel model
            self.panels[-1].params.sun_frame_ptr(self.sun.outputs.inertial_frame())
            self.panels[-1].params.r_sun(self.sun.outputs.eq_radius())
            self.panels[-1].params.planet_frame_ptr(self.earth.outputs.inertial_frame())
            self.panels[-1].params.r_planet(self.earth.outputs.eq_radius())



#########################################################
# CustomSpacecraft Battery Configuration Method
#########################################################
    def configBatteryFromJson(self, battery_name, initial_charge=1.0):
        '''
        JSON files for the battery are saved in the directory 
        './custom_battery_json'. Each JSON file corresponds 
        to a battery that you are considering using.

        INPUTS
        battery_name (string):
            Name of the battery you wish to config CustomSpacecraft with, the name 
            should match the name of the JSON file and manufacturer provided name.
        initial_charge (float) [optional]:
            The initial percentage charge of the battery, value between 0 and 1,
            with 1 being fully charged and 0 being initially empty. Default is 1.
        '''
        # Create the battery and configure it from the JSON file
        self.battery = SimpleBatterySystem(self._exc, "CustomSpacecraft_battery")
        json_path = os.path.join(os.path.dirname(__file__), 'custom_battery_json', battery_name + '.json')
        error = self.battery.configureFromJson(json_path)
        if error != 0:
            print("Error with battery configure method! Check if input name is correct")
            sys.exit(1)

        # Set the initial charge of the battery [%]
        self.battery.params.initial_charge_state(initial_charge)

        # Set the cut-off capacity as 40% denoting the autonomous mission mode change
        # based on a power SOH fault. This is a standard autonomous procedure.
        self.battery.params.shutoff_capacity(0.4)



#########################################################
# CustomSpacecraft Ground Station Configuration Method
#########################################################
    def configGroundStation(self, name='ATTX', latitude=39.97630*DEGREES_TO_RADIANS, longitude=-105.06616*DEGREES_TO_RADIANS):
        '''
        Creates an attribute that is an array of ground stations that the user has
        configured. When creating a ground station, you must pass in the name of
        the ground station you wish to refer to it as, as well as the latitude and
        longitude of the ground station [in degrees].

        Continuously calling this method will continue to add ground stations to the
        array which allows for multiple ground stations. The default is a fake ground
        station located at the ATTX office space.

        INPUTS
        name (string) [optional]:
            Name of the ground station, only used as a reference to the model name.
            Defaults to fake ATTX ground station.
        latitude (float) [optional]:
            Detic latitude of the ground station in degrees.
        longitude (float) [optional]:
            longitude of the ground station in degrees.
        
        OUTPUT
        index (integer):
            Integer of the ground station list that was added in this method call.
        '''
        # Check if CustomSpacecraft has attribute for ground station list
        # If not, create it
        if not hasattr(self, 'ground_stations'):
            self.ground_stations = []
        
        # Add ground station to end
        self.ground_stations.append(GroundStationModel(self._exc, name))
        # Configure ground station based on inputs
        self.ground_stations[-1].params.spacecraft_frame(self.body())
        self.ground_stations[-1].params.planet_rotating_frame(self.earth.outputs.rotating_frame())
        self.ground_stations[-1].params.latitude_detic_rad(latitude)
        self.ground_stations[-1].params.longitude_rad(longitude)

        # Return index of added ground station
        return len(self.ground_stations)-1
