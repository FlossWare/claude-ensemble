#!/bin/bash

# Node Health Monitor
# Collects CPU, temperature, RAM, and I/O metrics for fleet nodes
# Returns health score (0-100) based on penalty system

set -euo pipefail

# Node list
NODES=("laptop-01" "aio-01" "server-01" "server-02" "server-03")

# ANSI color codes
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Function to get metrics from a node
get_node_metrics() {
    local node=$1
    local is_local=0
    
    # Check if this is the local node
    if [[ "$(hostname)" == "$node" ]]; then
        is_local=1
    fi
    
    # CPU load (1-min average)
    if [[ $is_local -eq 1 ]]; then
        load=$(uptime | awk '{print $(NF-2)}' | tr -d ',')
    else
        load=$(ssh -o ConnectTimeout=5 "$node" "uptime" 2>/dev/null | awk '{print $(NF-2)}' | tr -d ',')
    fi
    
    # Temperature (average of all cores)
    if [[ $is_local -eq 1 ]]; then
        temp=$(sensors 2>/dev/null | grep -E "Core|Package" | awk '{print $3}' | tr -d '+°C' | awk '{sum+=$1; n++} END {if(n>0) print sum/n; else print 0}')
    else
        temp=$(ssh -o ConnectTimeout=5 "$node" "sensors 2>/dev/null | grep -E 'Core|Package' | awk '{print \$3}'" 2>/dev/null | tr -d '+°C' | awk '{sum+=$1; n++} END {if(n>0) print sum/n; else print 0}')
    fi
    
    # RAM available (MB)
    if [[ $is_local -eq 1 ]]; then
        ram=$(free -m | grep Mem | awk '{print $7}')
    else
        ram=$(ssh -o ConnectTimeout=5 "$node" "free -m" 2>/dev/null | grep Mem | awk '{print $7}')
    fi
    
    # I/O wait percentage
    if [[ $is_local -eq 1 ]]; then
        iowait=$(top -bn1 | grep "Cpu(s)" | awk '{print $10}' | tr -d '%wa,')
    else
        iowait=$(ssh -o ConnectTimeout=5 "$node" "top -bn1" 2>/dev/null | grep "Cpu(s)" | awk '{print $10}' | tr -d '%wa,')
    fi
    
    # Handle connection failures
    if [[ -z "$load" ]]; then load=0; fi
    if [[ -z "$temp" ]]; then temp=0; fi
    if [[ -z "$ram" ]]; then ram=0; fi
    if [[ -z "$iowait" ]]; then iowait=0; fi
    
    echo "$load|$temp|$ram|$iowait"
}

# Function to calculate health score
calculate_health_score() {
    local load=$1
    local temp=$2
    local ram=$3
    local iowait=$4
    
    local score=100
    
    # Penalty: -10 per load point above 4.0
    if (( $(echo "$load > 4.0" | bc -l) )); then
        local load_penalty=$(echo "($load - 4.0) * 10" | bc -l)
        score=$(echo "$score - $load_penalty" | bc -l)
    fi
    
    # Penalty: -5 per 10°C above 60°C
    if (( $(echo "$temp > 60" | bc -l) )); then
        local temp_penalty=$(echo "($temp - 60) / 10 * 5" | bc -l)
        score=$(echo "$score - $temp_penalty" | bc -l)
    fi
    
    # Penalty: -20 if RAM < 2GB available
    if (( $(echo "$ram < 2048" | bc -l) )); then
        score=$(echo "$score - 20" | bc -l)
    fi
    
    # Penalty: -10 per 1% I/O wait above 5%
    if (( $(echo "$iowait > 5" | bc -l) )); then
        local io_penalty=$(echo "($iowait - 5) * 10" | bc -l)
        score=$(echo "$score - $io_penalty" | bc -l)
    fi
    
    # Clamp score to 0-100 range
    if (( $(echo "$score < 0" | bc -l) )); then
        score=0
    fi
    if (( $(echo "$score > 100" | bc -l) )); then
        score=100
    fi
    
    printf "%.1f" "$score"
}

# Function to get color based on score
get_score_color() {
    local score=$1
    if (( $(echo "$score >= 80" | bc -l) )); then
        echo -e "${GREEN}"
    elif (( $(echo "$score >= 60" | bc -l) )); then
        echo -e "${YELLOW}"
    else
        echo -e "${RED}"
    fi
}

# Main monitoring loop
echo "Fleet Node Health Monitor"
echo "=========================="
echo ""

for node in "${NODES[@]}"; do
    echo "Checking $node..."
    
    metrics=$(get_node_metrics "$node")
    IFS='|' read -r load temp ram iowait <<< "$metrics"
    
    if [[ "$load" == "0" && "$temp" == "0" && "$ram" == "0" && "$iowait" == "0" ]]; then
        echo -e "${RED}  [OFFLINE]${NC}"
        echo ""
        continue
    fi
    
    score=$(calculate_health_score "$load" "$temp" "$ram" "$iowait")
    color=$(get_score_color "$score")
    
    echo "  CPU Load:    $load"
    echo "  Temperature: ${temp}°C"
    echo "  RAM Avail:   ${ram} MB"
    echo "  I/O Wait:    ${iowait}%"
    echo -e "  ${color}Health Score: ${score}/100${NC}"
    echo ""
done

# JSON output option
if [[ "${1:-}" == "--json" ]]; then
    echo "{"
    first=1
    for node in "${NODES[@]}"; do
        metrics=$(get_node_metrics "$node")
        IFS='|' read -r load temp ram iowait <<< "$metrics"
        
        if [[ "$load" == "0" && "$temp" == "0" && "$ram" == "0" && "$iowait" == "0" ]]; then
            continue
        fi
        
        score=$(calculate_health_score "$load" "$temp" "$ram" "$iowait")
        
        if [[ $first -eq 0 ]]; then
            echo ","
        fi
        first=0
        
        cat << JSON
  "$node": {
    "load": $load,
    "temperature": $temp,
    "ram_available_mb": $ram,
    "io_wait_percent": $iowait,
    "health_score": $score
  }
JSON
    done
    echo "}"
fi
