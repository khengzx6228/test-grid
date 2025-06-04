#!/bin/bash

# Grid Trading System - Deployment Script
# Version: 2.0 - Fixed and Enhanced
# 
# This script automates the deployment of the Grid Trading System
# Compatible with Linux, macOS, and Windows (via WSL/Git Bash)

set -e  # Exit on any error

# Color definitions for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
PYTHON_MIN_VERSION="3.8"
VENV_NAME="venv"
CONFIG_FILE="config.yaml"
LOG_DIR="logs"
DATA_DIR="data"
BACKUP_DIR="backups"

# Print functions
print_banner() {
    echo -e "${BLUE}"
    echo "════════════════════════════════════════════════════════════════"
    echo "🚀 Grid Trading System Deployment Script v2.0"
    echo "════════════════════════════════════════════════════════════════"
    echo "Advanced Cryptocurrency Trading Bot - Fixed Version"
    echo "✨ Automated Setup & Configuration"
    echo "✨ Multi-layer Grid Strategy"
    echo "✨ Real-time Web Monitoring"
    echo "✨ Risk Management & Safety Features"
    echo "════════════════════════════════════════════════════════════════"
    echo -e "${NC}"
}

print_info() {
    echo -e "${CYAN}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${PURPLE}[STEP]${NC} $1"
}

# Utility functions
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

version_compare() {
    printf '%s\n%s\n' "$2" "$1" | sort -V -C
}

get_python_version() {
    python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0"
}

detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "msys" ]]; then
        echo "windows"
    else
        echo "unknown"
    fi
}

# System requirements check
check_system_requirements() {
    print_step "Checking system requirements..."
    
    local os_type=$(detect_os)
    print_info "Detected OS: $os_type"
    
    # Check Python
    if ! command_exists python3; then
        print_error "Python 3 is not installed"
        print_info "Please install Python 3.8+ from https://python.org"
        return 1
    fi
    
    local python_version=$(get_python_version)
    print_info "Python version: $python_version"
    
    if ! version_compare "$python_version" "$PYTHON_MIN_VERSION"; then
        print_error "Python $PYTHON_MIN_VERSION or higher is required (found $python_version)"
        return 1
    fi
    
    # Check pip
    if ! command_exists pip3; then
        print_error "pip3 is not installed"
        print_info "Installing pip..."
        python3 -m ensurepip --upgrade || {
            print_error "Failed to install pip"
            return 1
        }
    fi
    
    # Check git (optional but recommended)
    if ! command_exists git; then
        print_warning "Git is not installed - some features may be limited"
    fi
    
    print_success "System requirements check completed"
    return 0
}

# Virtual environment setup
setup_virtual_environment() {
    print_step "Setting up Python virtual environment..."
    
    if [[ -d "$VENV_NAME" ]]; then
        print_info "Virtual environment already exists"
        read -p "Do you want to recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Removing existing virtual environment..."
            rm -rf "$VENV_NAME"
        else
            print_info "Using existing virtual environment"
            return 0
        fi
    fi
    
    print_info "Creating virtual environment..."
    python3 -m venv "$VENV_NAME" || {
        print_error "Failed to create virtual environment"
        return 1
    }
    
    print_success "Virtual environment created successfully"
    return 0
}

# Activate virtual environment
activate_virtual_environment() {
    print_info "Activating virtual environment..."
    
    if [[ -f "$VENV_NAME/bin/activate" ]]; then
        source "$VENV_NAME/bin/activate"
    elif [[ -f "$VENV_NAME/Scripts/activate" ]]; then
        source "$VENV_NAME/Scripts/activate"
    else
        print_error "Virtual environment activation script not found"
        return 1
    fi
    
    # Upgrade pip
    print_info "Upgrading pip..."
    pip install --upgrade pip || {
        print_warning "Failed to upgrade pip - continuing anyway"
    }
    
    print_success "Virtual environment activated"
    return 0
}

# Install dependencies
install_dependencies() {
    print_step "Installing Python dependencies..."
    
    if [[ ! -f "requirements.txt" ]]; then
        print_error "requirements.txt not found"
        print_info "Please ensure requirements.txt is in the current directory"
        return 1
    fi
    
    print_info "Installing dependencies from requirements.txt..."
    pip install -r requirements.txt || {
        print_error "Failed to install dependencies"
        print_info "This might be due to:"
        print_info "1. Network connectivity issues"
        print_info "2. Missing system dependencies"
        print_info "3. Incompatible package versions"
        return 1
    }
    
    print_success "Dependencies installed successfully"
    return 0
}

# Create necessary directories
create_directories() {
    print_step "Creating necessary directories..."
    
    local directories=("$LOG_DIR" "$DATA_DIR" "$BACKUP_DIR" "config")
    
    for dir in "${directories[@]}"; do
        if [[ ! -d "$dir" ]]; then
            mkdir -p "$dir"
            print_info "Created directory: $dir"
        else
            print_info "Directory already exists: $dir"
        fi
    done
    
    # Set appropriate permissions
    chmod 755 "$LOG_DIR" "$DATA_DIR" "$BACKUP_DIR" 2>/dev/null || true
    
    print_success "Directory structure created"
    return 0
}

# Setup configuration
setup_configuration() {
    print_step "Setting up configuration..."
    
    if [[ -f "$CONFIG_FILE" ]]; then
        print_info "Configuration file already exists"
        read -p "Do you want to backup and recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            local backup_name="${CONFIG_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
            cp "$CONFIG_FILE" "$backup_name"
            print_info "Backed up existing config to: $backup_name"
        else
            print_info "Using existing configuration file"
            return 0
        fi
    fi
    
    print_info "Creating default configuration file..."
    
    # Check if we have the config template in the artifacts
    if [[ -f "config_template.yaml" ]]; then
        cp "config_template.yaml" "$CONFIG_FILE"
    else
        # Create a minimal config if template is not available
        cat > "$CONFIG_FILE" << 'EOF'
# Basic Grid Trading System Configuration
trading:
  symbol: "BTCUSDT"
  leverage: 1
  initial_balance: 1000
  grid_configs:
    high_freq:
      range: 0.03
      spacing: 0.005
      size: 20
    main_trend:
      range: 0.15
      spacing: 0.01
      size: 50
    insurance:
      range: 0.50
      spacing: 0.05
      size: 100
  risk_management:
    max_drawdown: 0.20
    stop_loss: 0.15

system:
  check_interval: 5
  web_port: 8080
  database_url: "sqlite:///data/trading.db"
  log_level: "INFO"

api:
  binance_api_key: "YOUR_API_KEY_HERE"
  binance_api_secret: "YOUR_API_SECRET_HERE"
  use_testnet: true

features:
  multi_symbol:
    enabled: false
  ai_optimization:
    enabled: false
  notifications:
    enabled: false

notifications:
  telegram:
    token: ""
    chat_id: ""
EOF
    fi
    
    print_success "Configuration file created: $CONFIG_FILE"
    print_warning "⚠️  IMPORTANT: Please edit $CONFIG_FILE and add your Binance API credentials"
    return 0
}

# Validate configuration
validate_configuration() {
    print_step "Validating configuration..."
    
    if [[ ! -f "$CONFIG_FILE" ]]; then
        print_error "Configuration file not found: $CONFIG_FILE"
        return 1
    fi
    
    # Use Python to validate the config
    python3 -c "
import yaml
import sys

try:
    with open('$CONFIG_FILE', 'r') as f:
        config = yaml.safe_load(f)
    
    # Check required sections
    required_sections = ['trading', 'system', 'api']
    for section in required_sections:
        if section not in config:
            print(f'Missing required section: {section}')
            sys.exit(1)
    
    # Check API keys
    api_key = config.get('api', {}).get('binance_api_key', '')
    if api_key == 'YOUR_API_KEY_HERE' or not api_key:
        print('Warning: Binance API key not configured')
        print('Please edit $CONFIG_FILE and add your API credentials')
    
    print('Configuration validation passed')
    
except yaml.YAMLError as e:
    print(f'YAML parsing error: {e}')
    sys.exit(1)
except Exception as e:
    print(f'Configuration validation error: {e}')
    sys.exit(1)
" || {
        print_error "Configuration validation failed"
        return 1
    }
    
    print_success "Configuration is valid"
    return 0
}

# Test system functionality
test_system() {
    print_step "Testing system functionality..."
    
    print_info "Testing configuration loading..."
    python3 main.py --check-config || {
        print_error "Configuration test failed"
        return 1
    }
    
    print_info "Testing database initialization..."
    python3 -c "
import asyncio
from core_system import DatabaseManager

async def test_db():
    db = DatabaseManager('sqlite:///data/test.db')
    success = await db.initialize()
    if success:
        print('Database test passed')
        return 0
    else:
        print('Database test failed')
        return 1

exit_code = asyncio.run(test_db())
exit(exit_code)
" || {
        print_error "Database test failed"
        return 1
    }
    
    # Clean up test database
    rm -f "data/test.db" 2>/dev/null || true
    
    print_success "System functionality tests passed"
    return 0
}

# Create service files
create_service_files() {
    print_step "Creating service management files..."
    
    # Create start script
    cat > "start.sh" << 'EOF'
#!/bin/bash
# Start Grid Trading System

cd "$(dirname "$0")"

# Activate virtual environment
if [[ -f "venv/bin/activate" ]]; then
    source venv/bin/activate
elif [[ -f "venv/Scripts/activate" ]]; then
    source venv/Scripts/activate
else
    echo "Virtual environment not found"
    exit 1
fi

# Start the system
python main.py "$@"
EOF
    
    # Create stop script
    cat > "stop.sh" << 'EOF'
#!/bin/bash
# Stop Grid Trading System

echo "Stopping Grid Trading System..."
pkill -f "python.*main.py" || true
echo "System stopped"
EOF
    
    # Create status script
    cat > "status.sh" << 'EOF'
#!/bin/bash
# Check Grid Trading System status

if pgrep -f "python.*main.py" > /dev/null; then
    echo "Grid Trading System is running"
    echo "PID: $(pgrep -f 'python.*main.py')"
    echo "Web interface: http://localhost:8080"
else
    echo "Grid Trading System is not running"
fi
EOF
    
    # Make scripts executable
    chmod +x start.sh stop.sh status.sh
    
    print_success "Service management scripts created"
    return 0
}

# Display final instructions
show_final_instructions() {
    print_success "🎉 Grid Trading System deployment completed successfully!"
    echo
    echo -e "${CYAN}📋 Next Steps:${NC}"
    echo "1. 🔑 Configure API credentials:"
    echo "   - Edit $CONFIG_FILE"
    echo "   - Add your Binance API key and secret"
    echo "   - Keep use_testnet: true for testing"
    echo
    echo "2. 🚀 Start the system:"
    echo "   - Run: ./start.sh"
    echo "   - Or: python main.py"
    echo
    echo "3. 🌐 Access web interface:"
    echo "   - Open: http://localhost:8080"
    echo "   - Monitor trades and system status"
    echo
    echo "4. 📊 Useful commands:"
    echo "   - Check status: ./status.sh"
    echo "   - Stop system: ./stop.sh"
    echo "   - View logs: tail -f logs/application_$(date +%Y%m%d).log"
    echo
    echo -e "${YELLOW}⚠️  Safety Reminders:${NC}"
    echo "   • Start with testnet (use_testnet: true)"
    echo "   • Use small amounts initially"
    echo "   • Monitor the system regularly"
    echo "   • Never invest more than you can afford to lose"
    echo
    echo -e "${GREEN}📚 Documentation:${NC}"
    echo "   • Configuration: $CONFIG_FILE"
    echo "   • Logs directory: $LOG_DIR/"
    echo "   • Data directory: $DATA_DIR/"
    echo "   • Backups: $BACKUP_DIR/"
    echo
    echo -e "${BLUE}🆘 Support:${NC}"
    echo "   • Check logs for errors"
    echo "   • Validate config: python main.py --check-config"
    echo "   • Test mode: Set mock_trading: true in config"
    echo
}

# Main deployment function
main() {
    print_banner
    
    # Check if we're in the right directory
    if [[ ! -f "main.py" ]]; then
        print_error "main.py not found. Please run this script from the project root directory."
        exit 1
    fi
    
    # Parse command line arguments
    local skip_deps=false
    local force_recreate=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-deps)
                skip_deps=true
                shift
                ;;
            --force-recreate)
                force_recreate=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [options]"
                echo "Options:"
                echo "  --skip-deps      Skip dependency installation"
                echo "  --force-recreate Force recreate virtual environment"
                echo "  --help           Show this help message"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Force recreate if requested
    if [[ "$force_recreate" == true ]]; then
        print_info "Force recreating environment..."
        rm -rf "$VENV_NAME"
    fi
    
    # Run deployment steps
    check_system_requirements || exit 1
    setup_virtual_environment || exit 1
    activate_virtual_environment || exit 1
    
    if [[ "$skip_deps" != true ]]; then
        install_dependencies || exit 1
    else
        print_info "Skipping dependency installation as requested"
    fi
    
    create_directories || exit 1
    setup_configuration || exit 1
    validate_configuration || exit 1
    test_system || exit 1
    create_service_files || exit 1
    
    show_final_instructions
    
    echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
    echo -e "${CYAN}🚀 Ready to start trading! Run: ./start.sh${NC}"
}

# Error handling
trap 'print_error "Deployment failed on line $LINENO. Check the error message above."' ERR

# Run main function
main "$@"