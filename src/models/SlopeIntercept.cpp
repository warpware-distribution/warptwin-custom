#include "SlopeIntercept.h"
#include "simulation/SimulationExecutive.h"

using namespace clockwerk;
using namespace warpos;

namespace warptwin {
    // These constructor functions can be largely ignored. These are boilerplate defaults
    // that only need to be modified when including a model within a model, or setting
    // variable values on construction. The only item worth noting is the START_STEP
    // in the first two instances of the constructor. This sets the default step for
    // the model to run in (see User's Guide for more info)
    SlopeIntercept::SlopeIntercept(Model &pnt, const std::string &m_name)  
            : Model(pnt, START_STEP, m_name) {}
    SlopeIntercept::SlopeIntercept(SimulationExecutive &e, const std::string &m_name) 
            : Model(e, START_STEP, m_name) {} 
    SlopeIntercept::SlopeIntercept(Model &pnt, int schedule_slot, const std::string &m_name) 
            : Model(pnt, schedule_slot, m_name) {}
    SlopeIntercept::SlopeIntercept(SimulationExecutive &e, int schedule_slot, const std::string &m_name) 
            : Model(e, schedule_slot, m_name) {}
    SlopeIntercept::~SlopeIntercept() {}

    int16 SlopeIntercept::activate() {
        // Define behavior to occur when the model is activated after deactivation
        // Here we just run execute, so outputs reflect the inputs once more.
        active(true);
        execute();

        // Model functions always return an error code. NO_ERROR means everything
        // went fine, and is an alias for 0. Anything nonzero is intepreted by
        // the sim as an error
        return NO_ERROR;
    }

    int16 SlopeIntercept::deactivate() {
        // Here behavior to deactivate the model is written. At a minimum it should
        // set the active flag to false, but we can also set up the model to show
        // it is deactivated. In slope intercept, we will set the outputs to 0.
        active(false);
        outputs.y(0.0);

        // Model functions always return an error code. NO_ERROR means everything
        // went fine, and is an alias for 0. Anything nonzero is intepreted by
        // the sim as an error
        return NO_ERROR;
    }

    int16 SlopeIntercept::start() {
        // Code used to configure the model goes here. This function runs once
        // at simulation start... Slope Intercept model doesn't have anything for
        // this, but this is where files should be loaded and items should be 
        // pre-calculated.

        // Model functions always return an error code. NO_ERROR means everything
        // went fine, and is an alias for 0. Anything nonzero is intepreted by
        // the sim as an error
        return NO_ERROR;
    }

    int16 SlopeIntercept::execute() {
        // Code which runs every model step goes here. Per the above and the User's
        // Guide, valid steps are START_STEP, DERIVATIVE, and END_STEP. In general
        // here is where you should write values to all outputs on the basis of 
        // inputs and params.
        outputs.y(params.m()*inputs.x() + params.b());

        // Model functions always return an error code. NO_ERROR means everything
        // went fine, and is an alias for 0. Anything nonzero is intepreted by
        // the sim as an error
        return NO_ERROR;
    }

}