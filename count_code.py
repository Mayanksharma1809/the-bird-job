import os

def count_code_metrics(start_path='.'):
    total_files = 0
    total_lines = 0
    total_bytes = 0
    extension_counts = {}
    
    exclude_dirs = {'.git', 'venv', '__pycache__', 'node_modules', '.cache'}
    include_extensions = {'.py', '.html', '.css', '.js', '.md', '.txt', '.pyi'}
    
    for root, dirs, files in os.walk(start_path):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in include_extensions:
                file_path = os.path.join(root, file)
                total_files += 1
                try:
                    file_size = os.path.getsize(file_path)
                    total_bytes += file_size
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        total_lines += len(lines)
                    
                    extension_counts[ext] = extension_counts.get(ext, 0) + len(lines)
                except Exception as e:
                    pass
    
    print(f"Total Files: {total_files}")
    print(f"Total Lines of Code: {total_lines}")
    print(f"Total Disk Size: {total_bytes / 1024:.2f} KB ({total_bytes / (1024*1024):.2f} MB)")
    print("\nLines by Extension:")
    for ext, count in sorted(extension_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {ext}: {count} lines")

if __name__ == "__main__":
    count_code_metrics()
