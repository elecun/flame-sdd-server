
#include "dk.sdd.inference.hpp"
#include <flame/log.hpp>

using namespace flame;

static dk_sdd_inference* _instance = nullptr;
flame::component::object* create(){ if(!_instance) _instance = new dk_sdd_inference(); return _instance; }
void release(){ if(_instance){ delete _instance; _instance = nullptr; }}

bool dk_sdd_inference::on_init(){

    try{

        /* get parameters from profile */
        json parameters = get_profile()->parameters();

        torch::Device device(torch::kCUDA);
        if(!torch::cuda::is_available()) {
            std::cerr << "CUDA is not available. Falling back to CPU." << std::endl;
            device = torch::Device(torch::kCPU);
        }

        if(parameters.contains("model")){
            string model = parameters["model"].get<string>();
            
            // model load
            torch::jit::script::Module module = torch::jit::load(model);
            module.to(device); // move the model to GPU
            module.eval();    // change inference mode

            // create input tensor (1x3x224x224 image)
            torch::Tensor input = torch::rand({1, 3, 224, 224});
            std::vector<int64_t> sizes = {1, 3, 224, 224};
            torch::Tensor input = torch::randn(sizes).to(device); // move the data to GPU
        }

    }
    catch (const c10::Error& e) {
        logger::error("Model Loading Error : {}", e.what());
        return false;
    }

    catch(json::exception& e){
        logger::error("Profile Error : {}", e.what());
        return false;
    }

    return true;
}

void dk_sdd_inference::on_loop(){
    

}

void dk_sdd_inference::on_close(){
    
}

void dk_sdd_inference::on_message(const component::message_t& msg){
    
}

void dk_sdd_inference::inference(){
    
    // inference
    std::vector<torch::jit::IValue> inputs;
    inputs.push_back(input);
    at::Tensor output = module.forward(inputs).toTensor();

    logger::info("Output tensor shape : {}", output.sizes());
    
}