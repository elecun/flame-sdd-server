
#include <regex>
#include <algorithm>
#include <cctype>
#include <string>
#include <vector>
#include <iostream>

using namespace std;


string target_dirname_regex(string mt_stand_raw){
    if(mt_stand_raw.empty()){
        return "Unknown";
    }

    auto trim = [](const string& input) -> string {
        const auto start = input.find_first_not_of(" \t\n\r");
        if(start == string::npos){
            return "";
        }
        const auto end = input.find_last_not_of(" \t\n\r");
        return input.substr(start, end - start + 1);
    };

    auto replace_slash = [](string input) -> string {
        std::replace(input.begin(), input.end(), '/', '_');
        return input;
    };

    if(mt_stand_raw.empty()){
        return "";
    }

    string raw = std::regex_replace(mt_stand_raw, std::regex("\\s+"), " ");
    raw = trim(raw);
    if(raw.empty()){
        return "";
    }

    if(!std::regex_search(raw, std::regex("[xX]"))){
        raw.erase(std::remove(raw.begin(), raw.end(), ' '), raw.end());
        return replace_slash(raw);
    }

    std::regex split_re("\\s*[xX]\\s*");
    std::sregex_token_iterator it(raw.begin(), raw.end(), split_re, -1);
    std::sregex_token_iterator end;
    vector<string> parts;
    for(; it != end; ++it){
        string token = trim(*it);
        if(!token.empty()){
            parts.push_back(token);
        }
    }
    if(parts.empty()){
        raw.erase(std::remove(raw.begin(), raw.end(), ' '), raw.end());
        return replace_slash(raw);
    }

    string first = parts.front();
    vector<string> rest(parts.begin() + 1, parts.end());

    std::smatch match;
    std::regex prefix_re("^([A-Za-z]+)\\s*([0-9].*)$");
    string prefix;
    string first_dim;
    if(std::regex_match(first, match, prefix_re)){
        prefix = match[1].str();
        first_dim = trim(match[2].str());
    }
    else{
        prefix = "";
        first_dim = first;
        first_dim.erase(std::remove(first_dim.begin(), first_dim.end(), ' '), first_dim.end());
    }

    vector<string> dims;
    dims.push_back(first_dim);
    dims.insert(dims.end(), rest.begin(), rest.end());

    string prefix_upper = prefix;
    std::transform(prefix_upper.begin(), prefix_upper.end(), prefix_upper.begin(),
                   [](unsigned char c){ return static_cast<char>(std::toupper(c)); });
    if(prefix_upper == "H" && dims.size() >= 2){
        dims.resize(2);
    }

    string joined;
    for(const auto& dim_raw : dims){
        string dim = dim_raw;
        dim.erase(std::remove(dim.begin(), dim.end(), ' '), dim.end());
        dim = replace_slash(dim);
        if(dim.empty()){
            continue;
        }
        if(!joined.empty()){
            joined += "x";
        }
        joined += dim;
    }

    string normalized = prefix.empty() ? joined : (prefix + joined);
    return normalized;

}

int main(){
    vector<string> inputs = {
        "H 194 x 150 x 6/9       ",
        "H 200 x 200 x 8/12      ",
        "H 200 x 204 x 12/12",
        "H 208 x 202 x 10/16",
        "H 244 x 175 x 7/11",
        "H 244 x 252 x 11/11",
        "H 248 x 249 x 8/13",
        "H 250 x 250 x 9/14",
        "H 250 x 255 x 14/14",
        "H 298 x 149 x 5.5/8",
        "H 300 x 150 x 6.5/9",
        "H 294 x 200 x 8/12",
        "H 298 x 201 x 9/14",
        "H 294 x 302 x 12/12",
        "H 298 x 299 x 9/14",
        "H 300 x 300 x 10/15",
        "H 300 x 305 x 15/15",
        "H 304 x 301 x 11/17",
        "H 310 x 305 x 15/20",
        "H 310 x 310 x 20/20",
        "H 346 x 174 x 6/9",
        "H 350 x 175 x 7/11",
        "H 354 x 176 x 8/13",
        "H 336 x 249 x 8/12",
        "H 340 x 250 x 9/14",
        "H 344 x 348 x 10/16",
        "H 344 x 354 x 16/16",
        "H 350 x 350 x 12/19",
        "H 350 x 357 x 19/19",
        "H 396 x 199 x 7/11",
        "H 400 x 200 x 8/13",
        "H 404 x 201 x 9/15",
        "H 386 x 299 x 9/14",
        "H 390 x 300 x 10/16",
        "H 388 x 402 x 15/15",
        "H 394 x 398 x 11/18",
        "H 394 x 405 x 18/18",
        "H 400 x 400 x 13/21",
        "H 400 x 408 x 21/21",
        "H 406 x 403 x 16/24",
        "H 414 x 405 x 18/28",
        "H 428 x 407 x 20/35",
        "H 458 x 417 x 30/50",
        "H 498 x 432 x 45/70",
        "H 446 x 199 x 8/12",
        "H 450 x 200 x 9/14",
        "H 434 x 299 x 10/15",
        "H 440 x 300 x 11/18",
        "H 496 x 199 x 9/14",
        "H 500 x 200 x 10/16",
        "H 506 x 201 x 11/19",
        "H 482 x 300 x 11/15",
        "H 488 x 300 x 11/18",
        "H 596 x 199 x 10/15",
        "H 600 x 200 x 11/17",
        "H 606 x 201 x 12/20",
        "H 612 x 202 x 13/23",
        "H 582 x 300 x 12/17",
        "H 582 x 300 x 12/17",
        "H 588 x 300 x 12/20",
        "H 594 x 302 x 14/23",
        "H 692 x 300 x 13/20",
        "H 700 x 300 x 13/24",
        "H 708 x 302 x 15/28",
        "W 8 x 31",
        "W 8 x 35",
        "W 8 x 40",
        "W 8 x 48",
        "W 8 x 58",
        "W 10 x 49",
        "W 10 x 60",
        "W 10 x 68",
        "W 10 x 77",
        "W 10 x 88",
        "W 10 x 100",
        "W 12 x 65",
        "W 12 x 72",
        "W 12 x 72",
        "W 12 x 79",
        "W 12 x 87",
        "W 12 x 96",
        "W 12 x 106",
        "W 12 x 120",
        "W 12 x 136",
        "W 12 x 8 x 40",
        "W 12 x 8 x 45",
        "W 12 x 8 x 50",
        "W 14 x 6-3/4 x 30",
        "W 14 x 6-3/4 x 34",
        "W 14 x 6-3/4 x 38",
        "W 14 x 14-1/2 x 90",
        "W 14 x 14-1/2 x 99",
        "W 14 x 14-1/2 x 109",
        "W 14 x 14-1/2 x 120",
        "HP 14 x 73",
        "HP 14 x 89",
        "HP 14 x 102",
        "HP 14 x 117",
        "HP 14 x 117",
        "W 14 x 14-1/2 x 132",
        "UB 203 x 133 x 25",
        "UB 203 x 133 x 30",
        "UB 356 x 171 x 45",
        "UB 356 x 171 x 51",
        "UB 356 x 171 x 57",
        "UB 356 x 171 x 67",
        "UC 356 x 368 x 129",
        "UC 356 x 368 x 153",
        "UC 356 x 368 x 177",
        "UC 203 x 203 x 46",
        "UC 203 x 203 x 52",
        "UC 203 x 203 x 60",
        "UC 203 x 203 x 71",
        "UC 203 x 203 x 86",
        "UC 254 x 254 x 73",
        "UC 254 x 254 x 89",
        "UC 254 x 254 x 107",
        "UC 254 x 254 x 132",
        "UC 305 x 305 x 97",
        "UC 305 x 305 x 118",
        "UC 305 x 305 x 137",
        "UC 305 x 305 x 158",
        "200 UB 22.3",
        "200 UB 25.4",
        "200 UB 29.8",
        "200 UC 46.2",
        "200 UC 52.2",
        "200 UC 59.5",
        "250 UB 25.7",
        "250 UC 72.9",
        "250 UC 89.5",
        "310 UB 32.0",
        "310 UB 40.4",
        "310 UB 46.2",
        "310 UC 96.8",
        "310 UC 118.0",
        "310 UC 137.0",
        "310 UC 158.0",
        "360 UB 44.7",
        "360 UB 50.7",
        "360 UB 56.7"
    };

    for(const auto& input : inputs){
        cout << input << " -> " << target_dirname_regex(input) << '\n';
    }
    return 0;
}
