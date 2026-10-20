#!/bin/bash
# oplire-reset Linux Installer
# Installs Cloudflare WARP on Linux

set -e

FORCE=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --force|-f)
            FORCE=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--force] [--verbose]"
            echo ""
            echo "Options:"
            echo "  --force, -f    Reinstall even if already installed"
            echo "  --verbose, -v  Show detailed output"
            echo "  --help, -h     Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root or use sudo"
    exit 1
fi

# Check if WARP already installed
if command -v warp-cli &> /dev/null; then
    if [ "$FORCE" = false ]; then
        echo "Cloudflare WARP is already installed"
        echo "Use --force to reinstall"
        exit 0
    fi
    echo "Reinstalling Cloudflare WARP..."
fi

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    echo "Cannot detect OS"
    exit 1
fi

echo "Installing Cloudflare WARP on $OS..."

case $OS in
    ubuntu|debian)
        echo "Installing for Debian/Ubuntu..."
        
        # Add repository
        curl -fsSL https://pkg.cloudflare.com/pubkey.gpg | gpg --yes -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg 2>/dev/null || true
        
        echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflare.com/ any main" > /etc/apt/sources.list.d/cloudflare-warp.list
        
        # Update and install
        apt-get update -qq
        apt-get install -y -qq cloudflare-warp || {
            echo "Failed to install cloudflare-warp"
            exit 1
        }
        ;;
    
    fedora|rhel|centos)
        echo "Installing for Fedora/RHEL..."
        
        # Add repository
        cat > /etc/yum.repos.d/cloudflare-warp.repo << EOF
[cloudflare-warp]
name=Cloudflare WARP
baseurl=https://pkg.cloudflare.com/epel-$VERSION_ID/
enabled=1
gpgcheck=1
gpgkey=https://pkg.cloudflare.com/pubkey.gpg
EOF
        
        dnf install -y -q cloudflare-warp || {
            echo "Failed to install cloudflare-warp"
            exit 1
        }
        ;;
    
    arch)
        echo "Installing for Arch Linux..."
        pacman -Sy --noconfirm cloudflare-warp || {
            echo "Failed to install cloudflare-warp"
            exit 1
        }
        ;;
    
    *)
        echo "Unsupported OS: $OS"
        echo "Please install manually: https://developers.cloudflare.com/warp-client/get-started/"
        exit 1
        ;;
esac

# Verify installation
if command -v warp-cli &> /dev/null; then
    echo "Cloudflare WARP installed successfully!"
    echo ""
    echo "To connect:"
    echo "  warp-cli connect"
    echo ""
    echo "To check status:"
    echo "  warp-cli status"
else
    echo "Warning: warp-cli not found in PATH"
    echo "Try logging out and back in"
fi