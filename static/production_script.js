document.addEventListener('DOMContentLoaded', function () {
    const itemSelect = document.getElementById('item');
    const batchNoSelect = document.getElementById('batch_no');

    itemSelect.addEventListener('change', function () {
        const selectedItem = this.value;
        updateBatchNumbers(selectedItem);
    });

    function updateBatchNumbers(item) {
        // Clear current options in Batch No dropdown
        batchNoSelect.innerHTML = '<option value="">Select a Batch No</option>';

        if (item) {
            fetch('/get_batch_numbers', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ selected_item: item }),
            })
            .then(response => response.json())
            .then(data => {
                // Populate Batch No dropdown with new options
                data.forEach(batchNo => {
                    const option = document.createElement('option');
                    option.value = batchNo;
                    option.textContent = batchNo;
                    batchNoSelect.appendChild(option);
                });
            })
            .catch(error => {
                console.error('Error fetching batch numbers:', error);
            });
        }
    }
});
