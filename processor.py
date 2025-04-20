import sys
import json
import tempfile
import os
import logging
from main import main  # Your existing processing functions

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='processor.log'
)

def run_processing(doc_id, request_path):
    try:
        # Load request data
        with open(request_path) as f:
            data = json.load(f)
        
        # Create temp workspace
        work_dir = tempfile.mkdtemp()
        os.chdir(work_dir)
        
        logging.info(f"Processing {doc_id} in {work_dir}")
        
        # Execute main processing
        main(data)
        
        logging.info("Processing completed")
        return True
        
    except Exception as e:
        logging.error(f"Failed: {str(e)}")
        return False
    finally:
        # Cleanup
        if os.path.exists(work_dir):
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)
        if os.path.exists(request_path):
            os.remove(request_path)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python processor.py <doc_id> <request_path>")
        sys.exit(1)
        
    success = run_processing(sys.argv[1], sys.argv[2])
    sys.exit(0 if success else 1)