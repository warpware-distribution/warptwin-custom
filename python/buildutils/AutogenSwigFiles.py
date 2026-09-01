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
import os, re, argparse

ITEM_NAME = "<<ItemName>>"
ITEM_PARAMS_CONTENT = "<<ItemParamsContent>>"
ITEM_INPUTS_CONTENT = "<<ItemInputsContent>>"
ITEM_OUTPUTS_CONTENT = "<<ItemOutputsContent>>"
INCLUDE_DIR = "<<IncludeDir>>"
CLOCKWERK_SWIG_DIR = "<<ClockwerkSwigPath>>"
NAMESPACE_NAME = "<<NamespaceName>>"

TEMPLATE_FILE = "swigtemplate.txt"

class AutogenSwigFiles:
    """
    This python class is used to auto-generate swig .i files for
    wrapping .cpp model and app files into other
    high-level languages.
    """
    # Define our internal variables for auto-generating swig files
    # Each of these must be set for our swig auto-generator to work

    def __init__(self, include_path, cwk_swig, output_file=None, template_file=TEMPLATE_FILE):
        """
        This function initializes the auto generator with appropriate information
        """
        self._item_params_content = None
        self._item_inputs_content = None
        self._item_outputs_content = None
        self._file_string = None
        self._input_string = None
        self._item_name = None
        self._include_path = include_path
        self._template_file = template_file
        self._output_file = output_file
        self._cwk_swig = cwk_swig
        self._namespace_name = None
        self._is_item = True

    def parseHeaderFile(self):
        """
        This function loads in the header file at include path as a string for
        parsing
        """
        with open(self._include_path, 'r') as file:
            self._input_string = file.read()
            file.close()

        if "Model" not in self._input_string and \
            "App" not in self._input_string and \
            "MODEL(" not in self._input_string:
            self._is_item = False

    def parseInputFile(self):
        """
        This function parses the input file from our text template and saves
        it to our string variable
        """
        with open(self._template_file, 'r') as file:
            self._file_string = file.read()
            file.close()

        # Get our object name via regular expression
        try:
            header = self._include_path[max(loc for loc, val in enumerate(self._include_path) if val == '/'):]
        except:
            header = self._include_path
        self._item_name = self._getStringBetweenMarkers("/", ".h", header)
        
        # Get our namespace name via regular expression
        tmp = self._input_string.split("namespace")
        if(len(tmp) < 2):
            self._namespace_name = ""
        else:
            tmp = tmp[1].split("{")
            if(len(tmp) < 2):
                self._namespace_name = ""
            else:
                tmp = tmp[0]
                tmp = tmp.strip() + "::"
                self._namespace_name = tmp# self._getStringBetweenMarkers("#include", "\n", self._input_string)

        if self._item_name is None:
            raise ValueError("Unable to parse item name from file input. Is it a .h?")
        
    def _getStringBetweenMarkers(self, start, end, parse):
        """
        A function to get the string between two text markers
        """
        # Split our string at our start delimeter
        start_split = parse.split(start)
        if len(start_split) != 2:
            return ""
        
        internal_split = start_split[-1].split(end)
        if len(internal_split) != 2:
            return ""

        return internal_split[0]

    def setValuesFromHeader(self):
        """
        This function parses the input header file for string information
        """
        # Use regular expressions to parse key markers from our file
        # First, find our params

        if "START_PARAMS" in self._input_string:
            self._item_params_content = self._getStringBetweenMarkers("START_PARAMS", "END_PARAMS", self._input_string)
        else:
            self._item_params_content = ""

        if "START_INPUTS" in self._input_string:
            self._item_inputs_content = self._getStringBetweenMarkers("START_INPUTS", "END_INPUTS", self._input_string)
        else:
            self._item_inputs_content = ""

        if "START_OUTPUTS" in self._input_string:
            self._item_outputs_content = self._getStringBetweenMarkers("START_OUTPUTS", "END_OUTPUTS", self._input_string)
        else:
            self._item_outputs_content = ""

    def customizeOutputFile(self):
        """
        This function customizes the file output by replacing template markers
        in our file string with actual desired values
        """
        self._file_string = self._file_string.replace(ITEM_NAME, self._item_name)
        self._file_string = self._file_string.replace(ITEM_PARAMS_CONTENT, self._item_params_content)
        self._file_string = self._file_string.replace(ITEM_INPUTS_CONTENT, self._item_inputs_content)
        self._file_string = self._file_string.replace(ITEM_OUTPUTS_CONTENT, self._item_outputs_content)
        self._file_string = self._file_string.replace(INCLUDE_DIR, self._include_path)
        self._file_string = self._file_string.replace(CLOCKWERK_SWIG_DIR, self._cwk_swig)
        self._file_string = self._file_string.replace(NAMESPACE_NAME, self._namespace_name)

        if self._item_params_content == "":
            self._file_string = self._file_string.replace("START_PARAMS };", "")
            self._file_string = self._file_string.replace("%rename ("+self._item_name+"_Params) "+self._namespace_name+self._item_name+"::Params;", "")
            self._file_string = self._file_string.replace("typedef " + self._namespace_name + self._item_name + "::Params Params;", "")
        if self._item_inputs_content == "":
            self._file_string = self._file_string.replace("START_INPUTS };", "")
            self._file_string = self._file_string.replace("%rename ("+self._item_name+"_Inputs) "+self._namespace_name+self._item_name+"::Inputs;", "")
            self._file_string = self._file_string.replace("typedef " + self._namespace_name + self._item_name + "::Inputs Inputs;", "")
        if self._item_outputs_content == "":
            self._file_string = self._file_string.replace("START_OUTPUTS };", "")
            self._file_string = self._file_string.replace("%rename ("+self._item_name+"_Outputs) "+self._namespace_name+self._item_name+"::Outputs;", "")
            self._file_string = self._file_string.replace("typedef " + self._namespace_name + self._item_name + "::Outputs Outputs;", "")

    def isItem(self):
        """
        Whether the header wraps something worth generating an interface for

        Only valid after parseHeaderFile
        """
        return self._is_item

    def outputFileName(self):
        """
        The bare name of the .i file this header generates, without any directory

        Only valid after parseInputFile
        """
        return self._item_name + '.i'

    def render(self):
        """
        Produce the interface file contents for this header without touching the filesystem

        Returns:
            The rendered .i contents, or None if the header does not wrap an item

        This is the whole generation pipeline in one call. Rendering separately from writing is
        what lets the caller compare against what is already on disk and leave an unchanged file
        alone -- CMake's SWIG integration treats a .i file's timestamp as a build dependency, so
        rewriting one with identical contents costs a re-run of SWIG and a recompile of that
        wrapper for nothing.
        """
        self.parseHeaderFile()
        if not self._is_item:
            return None
        self.parseInputFile()
        self.setValuesFromHeader()
        self.customizeOutputFile()
        return self._file_string

    def writeOutputFile(self):
        """
        This function writes out the string _file_string to our file address

        Returns:
            True if the file was written, False if it already held these contents
        """
        # Now determine where we're writing to. The directory is created recursively and
        # _output_file is left as given, so that calling this twice does not turn the directory
        # it names into a file path.
        directory = 'swig_auto' if self._output_file is None else self._output_file
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, self.outputFileName())

        if not self._is_item:
            return False

        return writeIfChanged(path, self._file_string)


def writeIfChanged(path, contents):
    """
    Write contents to path only if the file does not already hold exactly that

    Args:
        path The file to write
        contents The text the file should end up holding

    Returns:
        True if the file was written, False if it was already correct and was left untouched

    Leaving an unchanged file alone keeps its timestamp, which is what stops a reconfigure from
    forcing a rebuild of everything downstream of it.
    """
    if os.path.exists(path):
        try:
            with open(path, 'r') as file:
                if file.read() == contents:
                    return False
        except (OSError, UnicodeDecodeError):
            # Unreadable or not text: fall through and replace it
            pass

    with open(path, 'w') as file:
        file.write(contents)
    return True

if __name__ == "__main__":
    # Create our argument parser
    parser = argparse.ArgumentParser(prog='SWIG File Auto-Generator',
                                     description='Auto-generates SWIG .i files for warptwin')
    
    # Add our arguments for input
    parser.add_argument('--include_path')
    parser.add_argument('--incl_swig_dir')
    parser.add_argument('--out_dir')
    parser.add_argument('--template_file')

    # Parse our args
    args = parser.parse_args()
    if args.template_file is None:
        args.templage_file = TEMPLATE_FILE
    
    # Run each function in our class
    aswig = AutogenSwigFiles(args.include_path, args.incl_swig_dir, args.out_dir, template_file=args.template_file)
    if aswig.render() is not None:
        aswig.writeOutputFile()