import os
import zipfile

def should_include(filename):
    # Lista plików i folderów do pominięcia
    exclude = {
        '__pycache__',
        'venv',
        '.venv',
        '.git',
        'create_deploy_zip.py',
        '.DS_Store',
        '*.pyc',
        '*.log'
    }
    
    # Sprawdź czy plik/folder nie powinien być pominięty
    for pattern in exclude:
        if pattern in filename or filename.endswith('.pyc'):
            return False
    return True

def create_zip():
    # Nazwa pliku ZIP
    zip_filename = 'deploy_package.zip'
    
    # Utwórz nowy plik ZIP
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Przejdź przez wszystkie pliki w katalogu
        for root, dirs, files in os.walk('.'):
            # Pomiń wykluczone foldery
            dirs[:] = [d for d in dirs if should_include(d)]
            
            for file in files:
                if should_include(file):
                    file_path = os.path.join(root, file)
                    # Dodaj plik do ZIP z zachowaniem struktury katalogów
                    arcname = os.path.relpath(file_path, '.')
                    zipf.write(file_path, arcname)
    
    print(f'Created {zip_filename} successfully!')

if __name__ == '__main__':
    create_zip()
