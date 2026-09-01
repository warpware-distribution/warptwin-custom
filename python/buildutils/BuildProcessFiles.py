#!/usr/bin/env python3 
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
import os, re, argparse, json, sys, ast
from AutogenSwigFiles import AutogenSwigFiles, writeIfChanged

METADATA_KEY = 'metadata'
NODE_DATA_KEY = 'node_data'
FORMAT_KEY = 'format_version'

# Bumped when the shape of build_data.json changes in a way a reader has to know about
FORMAT_VERSION = 2

# Written into the output directory to record what this script generated. It is not read back --
# generation does not depend on it -- but it makes the contents of a build directory explainable
# without having to re-derive them.
MANIFEST_NAME = '.autogen_manifest'

PARAM = -1
INPUT = -2
OUTPUT = 1

# Type mapping
NUMERIC = 0
STRING = 1
POINTER = 2
VECTOR3 = 3
QUATERNION = 4
FRAME = 5
UNDEFINED = 6
MATRIX = 7
ARRAY = 8
TIME = 9
STD_VECTOR = 10
DEFINED_MAPS = {'int' : NUMERIC,
                'unsigned int' : NUMERIC,
                'bool' : NUMERIC,
                'double' : NUMERIC,
                'float' : NUMERIC,
                'long double' : NUMERIC,
                'std::string' : STRING}

MATRIX_MAP = {'2' : [2, 2],
              '3' : [3, 3],
              '4' : [4, 4],
              '6' : [6, 6],
              '21' : [2, 1],
              '31' : [3, 1],
              '41' : [4, 1],
              '61' : [6, 1],
              '63' : [6, 3]}

class BuildProcessFiles():
    """
    Process files and generate swig representations of them as well
    as json representations of models for interacting with the warptwin
    GUI, and any other build-based preprocessing necessary for all
    elements of WarpTwin to function properly. In general, the steps
    followed in this class are as follows:

    1. Render the SWIG interface for every target header, in memory
    2. Reconcile the output directory against what was rendered: write the files whose contents
       changed, leave the rest alone, and delete any that no longer have a header behind them
    3. Write the json describing every model's interface, for the warptwin GUI

    Change detection is by content, not by timestamp. The output of this script is a pure
    function of the target headers, the template and this code, so rendering everything and
    comparing against what is on disk answers "what needs to change" exactly, with none of the
    ways a timestamp comparison gets it wrong:

      - a header deleted, or one that stopped wrapping an item, used to leave its .i file behind
        for CMake to keep building against a class that no longer exists
      - a header restored with an older timestamp -- git stash pop, an rsync -t, a tarball --
        looked older than the last build and was skipped
      - the last build time was recorded as whole seconds while file times carry a fraction, so
        a header untouched since the last run still compared as newer and was rewritten every
        single configure
      - editing swigtemplate.txt, which every generated file is built from, changed nothing at
        all because no header's timestamp had moved

    Not rewriting an unchanged file is what keeps a reconfigure cheap: CMake's SWIG integration
    treats a .i file's timestamp as a build dependency, so a needless rewrite costs a full
    re-run of SWIG plus a recompile of that wrapper.
    """
    def __init__(self, target_files, info_file, swig_in_dir, swig_out_dir, swig_template_file, start_node=0, start_connection=0, py_module='warptwin'):
        """
        Initializes the Build processor with all information it needs to function

        Args:
            target_files: The list of .h files targeted by the build system as a semicolon-separated string
            info_file: The location of the info file to which build metadata is written
        """
        # Blank entries come from a trailing separator or an empty list, and duplicates from
        # overlapping globs. Sorting makes the generated ids and the json deterministic rather
        # than dependent on the order the build system happened to hand the targets over in.
        seen = set()
        self._target_files = []
        for target in target_files.split(";"):
            target = target.strip()
            if target and target not in seen:
                seen.add(target)
                self._target_files.append(target)
        self._target_files.sort()

        self._info_file = info_file
        self._swig_in_dir = swig_in_dir
        self._swig_out_dir = swig_out_dir
        self._swig_template_file = swig_template_file
        self._py_module = py_module

        # Rendered interfaces, keyed by output file name, and the header each came from
        self._rendered = {}
        self._sources = {}
        self._missing_targets = []

        # Counting variables for internal use
        self._unique_node_id = start_node
        self._unique_connection_id = start_connection

    def __call__(self):
        """
        Run the end to end build system
        """
        self.checkInputs()
        self.renderTargets()
        self.syncOutputDirectory()
        self.writeBuildConfiguration()

    def checkInputs(self):
        """
        Refuse to run against inputs that would produce a wrong or destructive result

        The output directory is reconciled against what was rendered, which includes deleting
        .i files that no longer belong. That is correct for a generated directory and ruinous
        for the hand-written one, so the two are not allowed to be the same place.
        """
        if not os.path.isfile(self._swig_template_file):
            raise SystemExit("BuildProcessFiles: template file not found: %s"
                             % self._swig_template_file)

        if os.path.abspath(self._swig_out_dir) == os.path.abspath(self._swig_in_dir):
            raise SystemExit("BuildProcessFiles: the output directory is the hand-written swig "
                             "directory (%s). Generated output is reconciled against the "
                             "targets, which would delete the hand-written interfaces."
                             % self._swig_in_dir)

        if not self._target_files:
            print("BuildProcessFiles: no target headers were given; "
                  "any previously generated interfaces will be removed")

    def renderTargets(self):
        """
        Render the SWIG interface for every target header, in memory

        Implicitly uses self._target_files, self._swig_in_dir, self._swig_out_dir and
        self._swig_template_file. Fills self._rendered and self._sources.
        """
        for target in self._target_files:
            # A header can disappear between the build system globbing for it and this script
            # running. That is not worth failing a configure over, but it is worth saying.
            if not os.path.isfile(target):
                self._missing_targets.append(target)
                continue

            aswig = AutogenSwigFiles(target, self._swig_in_dir, self._swig_out_dir,
                                     self._swig_template_file)
            contents = aswig.render()
            if contents is None:
                # Not a model, app or task -- nothing to wrap
                continue

            name = aswig.outputFileName()
            if name in self._rendered:
                raise SystemExit("BuildProcessFiles: %s and %s both generate %s. Two headers "
                                 "with the same file name cannot both be wrapped."
                                 % (self._sources[name], target, name))
            self._rendered[name] = contents
            self._sources[name] = target

    def syncOutputDirectory(self):
        """
        Make the output directory hold exactly the rendered interfaces and nothing else

        Files whose contents already match are left untouched, so their timestamps do not move
        and nothing downstream of them rebuilds. Files with no header behind them any more are
        removed, which is what a deleted -- or newly excluded -- model needs.
        """
        os.makedirs(self._swig_out_dir, exist_ok=True)

        written = 0
        for name in sorted(self._rendered):
            if writeIfChanged(os.path.join(self._swig_out_dir, name), self._rendered[name]):
                written += 1

        removed = []
        for existing in sorted(os.listdir(self._swig_out_dir)):
            if existing.endswith('.i') and existing not in self._rendered:
                os.remove(os.path.join(self._swig_out_dir, existing))
                removed.append(existing)

        writeIfChanged(os.path.join(self._swig_out_dir, MANIFEST_NAME),
                       "".join(name + "\n" for name in sorted(self._rendered)))

        for target in self._missing_targets:
            print("BuildProcessFiles: target header does not exist, skipping: %s" % target)
        for name in removed:
            print("BuildProcessFiles: removed %s -- no target header generates it any more"
                  % name)
        print("BuildProcessFiles: %d interface(s), %d written, %d unchanged, %d removed"
              % (len(self._rendered), written, len(self._rendered) - written, len(removed)))

    def writeBuildConfiguration(self):
        """
        Write the build metadata and model interfaces out to json file

        Implicitly uses self._info_file and self._target_files

        The contents are deterministic -- no timestamp -- so that a run which changed nothing
        leaves the file, and its timestamp, alone.
        """
        info = {}

        info[METADATA_KEY] = {FORMAT_KEY: FORMAT_VERSION}

        # And write out information on each model file
        info[NODE_DATA_KEY] = {}
        for target in self._target_files:
            if not os.path.isfile(target):
                continue
            tmp = self.modelDataAsDict(target)
            if tmp is not None:
                info[NODE_DATA_KEY][tmp['class_type']] = tmp

        writeIfChanged(self._info_file, json.dumps(info, indent=4) + "\n")

    def modelDataAsDict(self, model_header):
        """
        Get model data in dictionary form
        
        Params:
            model_header The header file from which contents should be loaded and processed
        """
        # Fill in our blank dictionary
        d = {}
        
        # Open our model header so we can parse the string data
        with open(model_header, 'r') as file:
            contents = file.read()
            file.close()

        if "Model" not in contents and \
            "Task" not in contents and \
            "Monitor" not in contents and \
            "Event" not in contents and \
            "MODEL(" not in contents:
            return None
        
        # Parse information from our imdata dictionary
        pattern = rf"imdata\s*=\s*(\{{(?:[^{{}}]*|\{{(?:[^{{}}]*|\{{.*?\}})*\}})*\}})"
        match = re.search(pattern, contents, re.DOTALL)
        imdata = {}
        if match:
            dict_str = match.group(1)  # Extract dictionary string
            try:
                imdata = ast.literal_eval(dict_str)  # Convert string to dictionary
            except:
                pass
        if 'exclude' in imdata and imdata['exclude']:
            return None
        
        # Parse information from our aliasing dictionary
        pattern = rf"aliases\s*=\s*(\{{(?:[^{{}}]*|\{{(?:[^{{}}]*|\{{.*?\}})*\}})*\}})"
        match = re.search(pattern, contents, re.DOTALL)
        aliases = {}
        if match:
            dict_str = match.group(1)  # Extract dictionary string
            try:
                aliases = ast.literal_eval(dict_str)  # Convert string to dictionary
            except:
                pass
        
        # Attempt to match the class name by regex -- return no match if we can't
        for key in ['Model', 'Task', 'Monitor', 'Event']:
            type_pattern = r'class\s+(\w+)\s*:\s*public\s+'+key+r'\s*\{'
            matches = re.findall(type_pattern, contents)
            if matches:
                d['class_type'] = matches[0]
                
        # If we do not find class type with the regex above, try using the MODEL macro
        if 'class_type' not in d:
            type_pattern = r'MODEL\s*\(\s*(\w+)\s*\)'
            matches = re.findall(type_pattern, contents)
            if matches:
                d['class_type'] = matches[0]
                
        if 'class_type' not in d:
            return None
        
        # Pull the class doxygen through so the GUI's node inspector can describe the model
        d['description'] = self.extractClassDescription(contents, d['class_type'])

        # Set our unique ID from a simple counter
        d['unique_id'] = self._unique_node_id
        
        # Set our node type too
        d['node_type'] = 1

        d['py_module'] = self._py_module
        
        # Set values from imnode. Both of these are always emitted, even when the header declares
        # no imdata: a missing key used to leave the field absent from the document, and the GUI's
        # node parser would then carry the previous model's value into it.
        if 'displayname' in imdata.keys():
            d['displayname'] = imdata['displayname']
        else:
            d['displayname'] = self.defaultDisplayName(d['class_type'])

        if 'category' in imdata.keys():
            d['category'] = imdata['category']
        else:
            d['category'] = 'Custom'
        
        # Get name of the class
        name_pattern = r''+d['class_type']+r'\([^)]*std::string\s+&\w+\s*=\s*"(.*?)"'
        matches = re.findall(name_pattern, contents, re.MULTILINE)
        if matches:
            d['name'] = matches[0]
        else:
            d['name'] = d['class_type'].lower()
        
        # Now match our param signals
        params = self.getStringBetweenMarkers('START_PARAMS', 'END_PARAMS', contents)
        info_p = self.processSignals(params, PARAM, aliases)
        if info_p is not None:
            d['inputs'] = info_p
        
        # Now match our input signals
        inputs = self.getStringBetweenMarkers('START_INPUTS', 'END_INPUTS', contents)
        info_i = self.processSignals(inputs, INPUT, aliases)
        if info_i is not None:
            if 'inputs' in d.keys():
                for key in info_i.keys():
                    d['inputs'][key] = info_i[key]
            else:
                d['inputs'] = info_i
        
        # Now match our param signals
        outputs = self.getStringBetweenMarkers('START_OUTPUTS', 'END_OUTPUTS', contents)
        info_o = self.processSignals(outputs, OUTPUT, aliases)
        if info_o is not None:
            d['outputs'] = info_o
        
        # Increment our class counter here -- we want to increment before any recursed
        # children but after we've had a chance to return if there's no match
        self._unique_node_id += 1
        
        return d
        
    def getStringBetweenMarkers(self, start_marker, end_marker, str):
        """
        Get the string between a string start and end marker

        Args:
            start_marker The start of the string
            end_marker The end of the string
            str The string to search

        Returns:
            The (non-inclusive) string between two markers or None if no match.
            Returns only the first match
        """
        pattern = r''+start_marker+'(.*?)'+end_marker+''
        matches = re.findall(pattern, str, re.DOTALL)
        
        if matches:
            return matches[0].strip()
        else:
            return None    
        
    def extractCppComments(self, text):
        pattern = r"/\*\*(.*?)\*/"  # Capture only the content inside /** and */
        matches = re.findall(pattern, text, re.DOTALL)

        # Strip leading/trailing whitespace from each comment
        return [match.strip() for match in matches]

    def defaultDisplayName(self, class_type):
        """
        Derive a readable node title from a class name

        Used when a model header declares no imdata displayname, so every node
        still arrives with a name of its own rather than being left blank.

        Args:
            class_type The name of the model class, e.g. 'FlatPlateDrag3D'

        Returns:
            The spaced-out name, e.g. 'Flat Plate Drag 3D'
        """
        # Split where a lower-case run meets an upper-case one, and where letters meet digits.
        # A digit followed by a capital is deliberately left alone, so a trailing dimension stays
        # attached: FlatPlateDrag3D reads "Flat Plate Drag 3D", not "Flat Plate Drag 3 D".
        spaced = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', class_type)
        spaced = re.sub(r'(?<=[A-Za-z])(?=\d)', ' ', spaced)
        spaced = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', spaced)
        return spaced.strip()

    def cleanDoxygenBlock(self, block):
        """
        Turn a raw doxygen comment body into readable prose

        Strips the leading '*' from each line, drops the @brief tag itself while
        keeping its text, and stops at the first other doxygen tag (@param,
        @note, ...) so the result is the class summary rather than its whole
        reference entry.

        Args:
            block The raw text found between /** and */

        Returns:
            The cleaned description as a single string, blank lines preserved
            as paragraph breaks
        """
        lines = []
        for raw_line in block.split('\n'):
            line = raw_line.strip()

            # Drop the comment gutter
            if line.startswith('*'):
                line = line[1:].strip()

            # @brief introduces the summary; any other tag ends it
            if line.startswith('@brief'):
                line = line[len('@brief'):].strip()
            elif line.startswith('@') or line.startswith('\\'):
                break

            lines.append(line)

        # Collapse the result, keeping paragraph breaks but not ragged wrapping
        paragraphs = []
        current = []
        for line in lines:
            if line:
                current.append(line)
            elif current:
                paragraphs.append(' '.join(current))
                current = []
        if current:
            paragraphs.append(' '.join(current))

        return '\n\n'.join(paragraphs).strip()

    def extractClassDescription(self, contents, class_type):
        """
        Pull the doxygen description that documents a model class

        Looks for the /** ... */ block immediately preceding the class
        declaration, which is where the model's @brief lives. This is what the
        GUI shows in its node inspector, so it is the class summary rather than
        any of the per-signal comments.

        Args:
            contents The full text of the model header
            class_type The name of the class to describe

        Returns:
            The cleaned description, or an empty string if the class carries no
            doxygen block
        """
        # Match the declaration, in any of the forms parseNodeData accepts: an explicit
        # 'class X : public Model', a bare 'class X', or the MODEL(X) macro
        declaration = None
        for pattern in (r'class\s+' + re.escape(class_type) + r'\s*:\s*public\s+\w+',
                        r'MODEL\s*\(\s*' + re.escape(class_type) + r'\s*\)',
                        r'class\s+' + re.escape(class_type) + r'\b'):
            declaration = re.search(pattern, contents)
            if declaration:
                break
        if not declaration:
            return ""

        # Consider the doxygen blocks that close before the declaration starts, keeping only
        # those that actually carry a summary. The model's own block is not always immediately
        # adjacent -- MODEL(X) is frequently declared below nested helper structs.
        preceding = contents[:declaration.start()]
        blocks = [match for match in re.finditer(r"/\*\*(.*?)\*/", preceding, re.DOTALL)
                  if '@brief' in match.group(1)]
        if not blocks:
            return ""

        last_block = blocks[-1]

        # Reject it if another model is declared in between: that block documents the other
        # model, not this one
        between = preceding[last_block.end():]
        if re.search(r'MODEL\s*\(|class\s+\w+\s*:\s*public\s+(Model|Task|Monitor|Event)\b',
                     between):
            return ""

        return self.cleanDoxygenBlock(last_block.group(1))
        
    def processSignals(self, str, connection_type, aliases):
        """
        Process all signal information out of a string and place it in a dict

        Args:
            str The string from which all signal information should be procesed
            connection_type The type of connection (param, input, output)
            aliases The visual naming aliases of the signals

        Returns:
            A dict containing all signal information
            
        Implicly uses self._unique_connection_id
        """
        # Create our empty dict, which we will fill with stuff
        connection_dict = {}
        
        # Break down signals into a string with the contents of our SIGNAL
        signal_pattern = r'SIGNAL\(([^()]*?(?:\([^()]*?\))*[^()]*)\)'
        matches = re.findall(signal_pattern, str)
        if not matches:
            return None
        
        # And pull in comments via descriptions
        descriptions = self.extractCppComments(str)
        
        # Break down the signal into a list of three arguments
        connections = []
        for match in matches:
            tmp = match.split(',')
            tmp_str = ''
            for val in tmp[2:]:
                tmp_str += ' ' + val
            connections.append([tmp[0].strip(), tmp[1].strip(), tmp_str.strip()])
        
        # Now parse information into our dict
        idx = 0
        for connection in connections:
            # Parse our description, cleaned the same way class descriptions are so the GUI
            # inspector shows prose rather than the raw comment gutter
            desc = ""
            if idx < len(descriptions):
                desc = self.cleanDoxygenBlock(descriptions[idx])
                
            if connection[0] in aliases.keys() and aliases[connection[0]] == 'EXCLUDE':
                pass
            else:
                connection_dict[connection[0]] = {'name' : connection[0],
                                                'unique_id' : self._unique_connection_id,
                                                'absolute_type' : connection[1],
                                                'paired_connection_id' : 0,
                                                'writable' : 0,
                                                'parent_node_id' : self._unique_node_id,
                                                'user_set' : 0,
                                                'connection_type' : connection_type,
                                                'description' : desc}
                
                type_dict = self.extractDataTypeInfo(connection[1], connection[2])
                for key in type_dict:
                    connection_dict[connection[0]][key] = type_dict[key]

                # An alias is the model author saying "this signal is meant to be wired up in the
                # editor". Params without one are configured by value in the inspector instead, so
                # the GUI uses this flag to keep them off the block. Every signal still appears in
                # the inspector regardless.
                if connection_dict[connection[0]]['name'] in aliases.keys():
                    connection_dict[connection[0]]['displayname'] = aliases[connection_dict[connection[0]]['name']]
                    connection_dict[connection[0]]['aliased'] = 1
                else:
                    connection_dict[connection[0]]['displayname'] = connection_dict[connection[0]]['name']
                    connection_dict[connection[0]]['aliased'] = 0
            
                self._unique_connection_id += 1
                
            idx += 1
            
        return connection_dict
    
    def extractDataTypeInfo(self, absolute_type, value_set):
        """
        Convert absolute type defined in file to reduced set of types defined for connections

        Args:
            absolute_type The absolute type set in the native c++ file
            value_set The string by which value is set in the native c++ file
            
        Return:
            A dictionary with the fields data_type, size, and values populated
        """
        type_dict = {'data_type':UNDEFINED,'size':[1,1],'values_0':[0]}
        # Manage a large if statement based on the contents of the absolute type
        if 'Frame' in absolute_type:
            # Our absolute type is a pointer. Set our native type to an integer
            type_dict['data_type'] = FRAME
            type_dict['size'] = [1,1]
            type_dict['values_0'] = ['0']
        elif '*' in absolute_type:
            # Our absolute type is a pointer. Set our native type to an integer
            type_dict['data_type'] = POINTER
            type_dict['size'] = [1,1]
            type_dict['values_0'] = ['0']
        elif 'Matrix' in absolute_type:
            type_dict['data_type'] = MATRIX
            if '<' in absolute_type:
                numbers = re.findall(r'\d+', absolute_type)
                type_dict['size'] = [int(numbers[0]), int(numbers[1])]
            else:
                numbers = re.findall(r'\d+', absolute_type)
                type_dict['size'] = MATRIX_MAP[numbers[0]]
            vals_dict = self.getValuesFromStrings(type_dict['size'], value_set)
            for key in vals_dict:
                type_dict[key] = vals_dict[key]
        elif 'CartesianVector' in absolute_type:
            type_dict['data_type'] = VECTOR3
            numbers = re.findall(r'\d+', absolute_type)
            type_dict['size'] = [1, int(numbers[0])]
            vals_dict = self.getValuesFromStrings(type_dict['size'], value_set)
            for key in vals_dict:
                type_dict[key] = vals_dict[key]
        elif 'Euler321' in absolute_type:
            type_dict['data_type'] = VECTOR3
            type_dict['size'] = [1, 3]
            vals_dict = self.getValuesFromStrings(type_dict['size'], value_set)
            for key in vals_dict:
                type_dict[key] = vals_dict[key]
        elif 'Quaternion' in absolute_type:
            type_dict['data_type'] = QUATERNION
            type_dict['size'] = [1, 4]
            vals_dict = self.getValuesFromStrings(type_dict['size'], value_set)
            for key in vals_dict:
                type_dict[key] = vals_dict[key]
        elif 'DCM' in absolute_type:
            type_dict['data_type'] = MATRIX
            type_dict['size'] = [3, 3]
            vals_dict = self.getValuesFromStrings(type_dict['size'], value_set)
            for key in vals_dict:
                type_dict[key] = vals_dict[key]
        elif 'MRP' in absolute_type:
            type_dict['data_type'] = VECTOR3
            type_dict['size'] = [1, 3]
            vals_dict = self.getValuesFromStrings(type_dict['size'], value_set)
            for key in vals_dict:
                type_dict[key] = vals_dict[key]
        elif 'array' in absolute_type:
            type_dict['data_type'] = ARRAY
            numbers = re.findall(r'\d+', absolute_type)
            type_dict['size'] = [1, int(numbers[1])]
            vals_dict = self.getValuesFromStrings(type_dict['size'], value_set)
            for key in vals_dict:
                type_dict[key] = vals_dict[key]
        elif 'vector' in absolute_type:
            type_dict['data_type'] = STD_VECTOR
            numbers = re.findall(r'\d+', absolute_type)
            if numbers:
                type_dict['size'] = [1, int(numbers[0])]
            else:
                type_dict['size'] = [1, 1]
            vals_dict = self.getValuesFromStrings(type_dict['size'], value_set)
            for key in vals_dict:
                type_dict[key] = vals_dict[key]
        elif 'Time' in absolute_type:
            type_dict['data_type'] = TIME
            type_dict['size'] = [1, 2]
            type_dict['values_0'] = ['0','0']
        else:
            # Our type is either native or not defined... this will resolve that
            if absolute_type in DEFINED_MAPS:
                type_dict['data_type'] = DEFINED_MAPS[absolute_type]
                type_dict['size'] = [1,1]
                type_dict['values_0'] = [value_set]
                
        return type_dict
    
    def getValuesFromStrings(self, size, set_string):
        """
        Set a dictionary row-wise given values set via string

        Args:
            size (_type_): A 2-D array describing the size of the values
            set_string The string by which values are set
        """

        value_dict = {}
        vals = []
        
        if '{' in set_string:
            # We already know we have an opening bracket, so split at opening brackets
            strings = set_string.split('{')
            strings_all = []
            # Discard first (before first bracket) and split again at closing brackets
            for s in strings[1:]:
                strings_all += s.split('}')
            # Discard last (after last bracket)
            strings = strings_all[:-1]
            # Eliminate all strings that contain only whitespace
            strings_tmp = [s.split(' ') for s in strings]
            strings_final = []
            for s in strings_tmp:
                strings_final.append([])
                for t in s:
                    if not t.isspace() and t != '':
                        strings_final[-1].append(t)
                if not strings_final[-1]:
                    del strings_final[-1]
            # Finally assign our values
            for i in range(len(strings_final)):
                value_dict['values_' + str(i)] = strings_final[i]
        else:
            numbers = re.findall(r'\d+', set_string)
            for i in range(size[0]):
                value_dict['values_' + str(i)] = ['0']*size[1]
        
        return value_dict
            
if __name__ == "__main__":
    # Create our argument parser
    parser = argparse.ArgumentParser(prog='Build pre-processor')
    
    # Add our arguments for input
    parser.add_argument('--targets')
    parser.add_argument('--info-file')
    parser.add_argument('--incl_swig_dir')
    parser.add_argument('--out_dir')
    parser.add_argument('--template_file')
    parser.add_argument('--start-node', default=0, type=int)
    parser.add_argument('--start-connection', default=0, type=int)
    parser.add_argument('--py-module', default='warptwin', type=str)
    args = parser.parse_args()
    
    bp = BuildProcessFiles(args.targets, 
                           args.info_file, 
                           args.incl_swig_dir, 
                           args.out_dir, 
                           args.template_file,
                           args.start_node,
                           args.start_connection,
                           args.py_module)
    bp()