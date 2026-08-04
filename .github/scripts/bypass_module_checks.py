import sys
import re

def patch_crc(content):
    # Match bad_version label inside check_version / module loader
    if "bad_version:" in content:
        pattern = r'(bad_version:\s*\n\t*)(return\s+0;)'
        if re.search(pattern, content):
            new_content = re.sub(pattern, r'\1return 1;', content)
            return new_content, True
        
        # Fallback if indent/formatting differs slightly
        pattern_fallback = r'(bad_version:.*?\n\s*)(return\s+0;)'
        if re.search(pattern_fallback, content, re.DOTALL):
            new_content = re.sub(pattern_fallback, r'\1return 1;', content, flags=re.DOTALL)
            return new_content, True
            
    return content, False

def patch_signing(content):
    # Find module_sig_check (handle prototypes vs definitions)
    for match in re.finditer(r'(?:static\s+)?int\s+module_sig_check', content):
        start_pos = match.start()
        brace_pos = content.find('{', start_pos)
        semicolon_pos = content.find(';', start_pos)
        
        # If we find a '{' before a ';', it's the function body
        if brace_pos != -1 and (semicolon_pos == -1 or brace_pos < semicolon_pos):
            new_content = content[:brace_pos + 1] + "\n\treturn 0;\n" + content[brace_pos + 1:]
            return new_content, True
            
    return content, False

def patch_namespace(content):
    # Find verify_namespace_is_imported (handle prototypes vs definitions)
    for match in re.finditer(r'(?:static\s+)?int\s+verify_namespace_is_imported', content):
        start_pos = match.start()
        brace_pos = content.find('{', start_pos)
        semicolon_pos = content.find(';', start_pos)
        
        # If we find a '{' before a ';', it's the function body
        if brace_pos != -1 and (semicolon_pos == -1 or brace_pos < semicolon_pos):
            new_content = content[:brace_pos + 1] + "\n\treturn 0;\n" + content[brace_pos + 1:]
            return new_content, True
            
    return content, False

def main():
    if len(sys.argv) < 2:
        print("Usage: bypass_module_checks.py <kernel_common_dir>")
        sys.exit(1)
        
    common_dir = sys.argv[1]
    print(f"[INFO] Patching kernel module loader in {common_dir}...")
    
    # Possible file locations depending on kernel version (5.10 vs 6.1+)
    files_to_check = [
        f"{common_dir}/kernel/module.c",
        f"{common_dir}/kernel/module/main.c",
        f"{common_dir}/kernel/module/version.c",
        f"{common_dir}/kernel/module/signing.c"
    ]
    
    patched_any = False
    
    for file_path in files_to_check:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except FileNotFoundError:
            continue
            
        modified = False
        
        # 1. Patch CRC check
        content, p_crc = patch_crc(content)
        if p_crc:
            print(f"  [+] Patched CRC check in {file_path}")
            modified = True
            
        # 2. Patch Signature check
        content, p_sig = patch_signing(content)
        if p_sig:
            print(f"  [+] Patched module signature check in {file_path}")
            modified = True
            
        # 3. Patch Namespace check
        content, p_ns = patch_namespace(content)
        if p_ns:
            print(f"  [+] Patched namespace import check in {file_path}")
            modified = True
            
        if modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            patched_any = True
            
    if patched_any:
        print("[SUCCESS] Kernel module loader checks bypassed successfully.")
    else:
        print("[WARNING] No module loader files were patched. Check directory structure or file patterns.")

if __name__ == "__main__":
    main()
