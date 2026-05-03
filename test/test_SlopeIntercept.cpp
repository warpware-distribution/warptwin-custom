#include <gtest/gtest.h>
#include "testtools.hpp"

#include "simulation/SimulationExecutive.h"
#include "models/SlopeIntercept.h"

using namespace clockwerk;
using namespace warpos;
using namespace warptwin;

/****************************************************
* @brief Example test showing how to use unit tests for new models
****************************************************/
TEST(warptwin_custom, SlopeInterceptExample) {
    // Build our gravity model
    SimulationExecutive exc;
    SlopeIntercept slope_intercept(exc);

    // Set our params and inputs
    slope_intercept.params.m(2.0);
    slope_intercept.params.b(3.0);

    slope_intercept.inputs.x(5.0);

    // Step the simulation executive
    int error = exc.startup();
    EXPECT_EQ(NO_ERROR, error);

    error = exc.step();
    EXPECT_EQ(NO_ERROR, error);

    // And verify our expected result
    EXPECT_DOUBLE_EQ(13.0, slope_intercept.outputs.y());
}
