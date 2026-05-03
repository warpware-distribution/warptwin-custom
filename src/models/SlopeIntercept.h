/*
Metadata for MS GUI:
imdata = {"displayname" : "Slope Intercept Model",
          "exclude" : False,
          "category" : "Custom"
}
aliases = {"m" : "Multiplier",
           "b" : "Offset",
           "x" : "Input",
           "y" : "Output"
}
*/

#ifndef MODELS_SLOPE_INTERCEPT_H
#define MODELS_SLOPE_INTERCEPT_H

#include "simulation/Model.h" 

namespace warptwin {

    /**
     * @brief   Simple implementation of y = mx + b
    */
    MODEL(SlopeIntercept)
    public:
        // Model params
        //         NAME                     TYPE                    DEFAULT VALUE
        START_PARAMS
            /** The multiplier in y=mx+b */
            SIGNAL(m,                       double,                 1.0)
            /** The offset in y=mx+b */
            SIGNAL(b,                       double,                 0.0)
        END_PARAMS

        // Model inputs
        //         NAME                     TYPE                    DEFAULT VALUE
        START_INPUTS
            /** The model input every step */
            SIGNAL(x,                       double,                 0.0)
        END_INPUTS

        // Model outputs
        //         NAME                     TYPE                    DEFAULT VALUE
        START_OUTPUTS
            /** The output from y=mx+b */
            SIGNAL(y,                       double,                 0.0)
        END_OUTPUTS

        int16 activate() override;
        int16 deactivate() override;

    protected:
        int16 start() override;
        int16 execute() override; 
    };

}

#endif