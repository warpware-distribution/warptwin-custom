/******************************************************************************
* Copyright (c) ATTX Inc 2026. All Rights Reserved.
*
* This software and associated documentation (the "Software") are the 
* proprietary and confidential information of ATTX Inc. The Software is 
* furnished under a license agreement between ATTX and the user organization 
* and may be used or copied only in accordance with the terms of the agreement.
* Refer to 'license/attx_license.adoc' for standard license terms.
*
* EXPORT CONTROL NOTICE: THIS SOFTWARE MAY INCLUDE CONTENT CONTROLLED UNDER THE
* INTERNATIONAL TRAFFIC IN ARMS REGULATIONS (ITAR) OR THE EXPORT ADMINISTRATION 
* REGULATIONS (EAR99). No part of the Software may be used, reproduced, or 
* transmitted in any form or by any means, for any purpose, without the express 
* written permission of ATTX Inc.
******************************************************************************/
/*
Clockwerk Test Tools File
-------------------------
This file defines tools for use in testing all code from the clockwerk module.
It is support code for clockwerk_test.cpp.

Author: Alex Reynolds
*/

#ifndef CLOCKWERK_TEST_TOOLS_HPP
#define CLOCKWERK_TEST_TOOLS_HPP

#include <cmath>
#include <iostream>

#include "core/Matrix.hpp"

namespace clockwerk {
    // Arbitrary size for output strings in test tool
    const int OUTPUT_STRING_SIZE = 500;

    // @brief   Function to compare two matrices and return the result
    // @param   expected    The expected matrix (defined by tester)
    // @param   actual      The actual matrix (result of test)
    // @return  True if matrices match. False otherwise
    // Note: Assumes matrix getters have been tested/are working
    template<uint32 R, uint32 C>
    bool matrixCompare(Matrix<R, C> expected, Matrix<R, C> actual, bool print=false) {
        bool test_pass = true;

        // Compare the size of the two matrices to ensure they match
        std::pair<uint32, uint32> exp_size = expected.size();
        std::pair<uint32, uint32> act_size = actual.size();
        if(exp_size.first != act_size.first || exp_size.second != act_size.second) {
            test_pass = false;
        }

        // Now loop through matrices and ensure they match
        floating_point expected_val;
        floating_point actual_val;
        for(unsigned int i = 0; i < exp_size.first; i++) {
            for(unsigned int j = 0; j < exp_size.second; j++) {
                expected.get(i, j, expected_val);
                actual.get(i, j, actual_val);
                if(expected_val != actual_val) {
                    test_pass = false;
                }
                if(std::isnan(actual_val)) {
                    test_pass = false;
                }
            }
        }

        // Print if commanded or if test failed
        if(print || !test_pass) {
            char str_val[OUTPUT_STRING_SIZE];
            expected.str(str_val, OUTPUT_STRING_SIZE);
            std::cout<<"Expected:"<<std::endl;
            std::cout<<str_val<<std::endl;
            std::cout<<"Actual: "<<std::endl;
            actual.str(str_val, OUTPUT_STRING_SIZE);
            std::cout<<str_val<<std::endl;
        }

        return test_pass;
    }

    // @brief   Function to compare two matrices and return the result
    // @param   expected    The expected matrix (defined by tester)
    // @param   actual      The actual matrix (result of test)
    // @return  True if matrices match. False otherwise
    // Note: Assumes matrix getters have been tested/are working
    template<unsigned int R, unsigned int C>
    bool matrixCompareTol(Matrix<R, C> expected, Matrix<R, C> actual, const double &tolerance, bool print=false) {
        bool test_pass = true;

        // Compare the size of the two matrices to ensure they match
        std::pair<unsigned int, unsigned int> exp_size = expected.size();
        std::pair<unsigned int, unsigned int> act_size = actual.size();
        if(exp_size.first != act_size.first || exp_size.second != act_size.second) {
            test_pass = false;
        }

        // Now loop through matrices and ensure they match
        floating_point expected_val;
        floating_point actual_val;
        for(unsigned int i = 0; i < exp_size.first; i++) {
            for(unsigned int j = 0; j < exp_size.second; j++) {
                expected.get(i, j, expected_val);
                actual.get(i, j, actual_val);
                if(std::abs(expected_val - actual_val) > tolerance) {
                    test_pass = false;
                }
                if(std::isnan(actual_val)) {
                    test_pass = false;
                }
            }
        }

        // Print if commanded or if test failed
        if(print || !test_pass) {
            char str_val[OUTPUT_STRING_SIZE];
            expected.str(str_val, OUTPUT_STRING_SIZE);
            std::cout<<"Expected:"<<std::endl;
            std::cout<<str_val<<std::endl;
            std::cout<<"Actual: "<<std::endl;
            actual.str(str_val, OUTPUT_STRING_SIZE);
            std::cout<<str_val<<std::endl;
        }

        return test_pass;
    }

    // @brief   Function to compare two arrays and return the result
    // @param   expected    The expected array (defined by tester)
    // @param   actual      The actual array (result of test)
    // @return  True if arrays match. False otherwise
    template<unsigned long int N>
    bool arrayCompareTol(std::array<floating_point, N> expected, 
                         std::array<floating_point, N> actual, 
                         const double &tolerance, 
                         bool print=false) {
        bool test_pass = true;

        // Now loop through matrices and ensure they match
        for(unsigned int i = 0; i < N; i++) {
            if(std::abs(expected[i] - actual[i]) > tolerance) {
                test_pass = false;
            }
                if(std::isnan(actual[i])) {
                    test_pass = false;
                }
        }
        
        // Print if commanded or test failed
        if(print || !test_pass) {
            std::cout<<"Expected: [";
            for(unsigned int i = 0; i < N; i++) {
                std::cout<<expected[i];
                if(i < N - 1) {
                    std::cout<<" ";
                }
            }
            std::cout<<"]\nActual: [";
            for(unsigned int i = 0; i < N; i++) {
                std::cout<<actual[i];
                if(i < N - 1) {
                    std::cout<<" ";
                }
            }
            std::cout<<"]"<<std::endl;
        }

        return test_pass;
    }

}

#endif