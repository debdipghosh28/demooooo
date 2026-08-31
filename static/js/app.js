/**
 * ==================================================================================
 * Relivio MedPredict - Core Application & ESP32 Hub Controller
 * ==================================================================================
 */

document.addEventListener('DOMContentLoaded', () => {
    // --------------------------------------------------------------------------
    // DOM Elements - Core Form & App
    // --------------------------------------------------------------------------
    const predictionForm = document.getElementById('predictionForm');
    const predictBtn = document.getElementById('predictBtn');
    const resetBtn = document.getElementById('resetBtn');
    const themeToggle = document.getElementById('themeToggle');
    const toast = document.getElementById('toast');

    // Temperature elements
    const tempInput = document.getElementById('temperature');
    const tempSlider = document.getElementById('tempSlider');
    const tempUnitBtns = document.querySelectorAll('#tempUnitToggle .unit-btn');
    const tempUnitDisplay = document.getElementById('tempUnitDisplay');
    const tempIndicator = document.getElementById('tempIndicator');
    const feverSeveritySelect = document.getElementById('feverSeverity');

    // Sliders
    const aqiSlider = document.getElementById('aqi');
    const aqiChip = document.getElementById('aqiChip');
    const humiditySlider = document.getElementById('humidity');
    const humidityChip = document.getElementById('humidityChip');

    // BMI Calculator
    const toggleBmiCalc = document.getElementById('toggleBmiCalc');
    const bmiCalcBox = document.getElementById('bmiCalcBox');
    const calcHeight = document.getElementById('calcHeight');
    const calcWeight = document.getElementById('calcWeight');
    const bmiInput = document.getElementById('bmi');

    // Results container elements
    const resultPlaceholder = document.getElementById('resultPlaceholder');
    const resultContent = document.getElementById('resultContent');
    const predictionHero = document.getElementById('predictionHero');
    const medName = document.getElementById('medName');
    const medTypeLabel = document.getElementById('medTypeLabel');
    const confidenceBadge = document.getElementById('confidenceBadge');
    const medIcon = document.getElementById('medIcon');
    const paracetamolProb = document.getElementById('paracetamolProb');
    const paracetamolFill = document.getElementById('paracetamolFill');
    const ibuprofenProb = document.getElementById('ibuprofenProb');
    const ibuprofenFill = document.getElementById('ibuprofenFill');
    const dosageText = document.getElementById('dosageText');
    const mechanismText = document.getElementById('mechanismText');
    const cautionsContainer = document.getElementById('cautionsContainer');
    const cautionsList = document.getElementById('cautionsList');
    const insightsContainer = document.getElementById('insightsContainer');
    const insightsList = document.getElementById('insightsList');
    const printReportBtn = document.getElementById('printReportBtn');
    const copyResultBtn = document.getElementById('copyResultBtn');

    // Model info accordion
    const toggleModelInfo = document.getElementById('toggleModelInfo');
    const modelInfoBody = document.getElementById('modelInfoBody');
    const infoChevron = document.getElementById('infoChevron');

    // Preset pills
    const presetPills = document.querySelectorAll('.preset-pill');

    // --------------------------------------------------------------------------
    // DOM Elements - ESP32 Telemetry HUD & Modal
    // --------------------------------------------------------------------------
    const openEsp32ModalBtn = document.getElementById('openEsp32ModalBtn');
    const closeEsp32ModalBtn = document.getElementById('closeEsp32ModalBtn');
    const esp32Modal = document.getElementById('esp32Modal');
    const headerIotRing = document.getElementById('headerIotRing');
    const headerIotLabel = document.getElementById('headerIotLabel');
    const hudConnectBtn = document.getElementById('hudConnectBtn');
    const hudLiveDot = document.getElementById('hudLiveDot');
    const hudLiveText = document.getElementById('hudLiveText');
    const hudDeviceName = document.getElementById('hudDeviceName');
    const hudProtocolBadge = document.getElementById('hudProtocolBadge');
    const hudAutoFillToggle = document.getElementById('hudAutoFillToggle');
    const hudAutoPredictToggle = document.getElementById('hudAutoPredictToggle');
    const ecgBpmVal = document.getElementById('ecgBpmVal');
    const hudPacketCounter = document.getElementById('hudPacketCounter');

    // HUD Vital Stat Tiles
    const hudTemp = document.getElementById('hudTemp');
    const hudTempChip = document.getElementById('hudTempChip');
    const hudHR = document.getElementById('hudHR');
    const hudHRChip = document.getElementById('hudHRChip');
    const hudSpO2 = document.getElementById('hudSpO2');
    const hudSpO2Chip = document.getElementById('hudSpO2Chip');
    const hudAQI = document.getElementById('hudAQI');
    const hudEnvChip = document.getElementById('hudEnvChip');

    // Quick Command Buttons
    const cmdSampleNow = document.getElementById('cmdSampleNow');
    const cmdToggleLed = document.getElementById('cmdToggleLed');
    const cmdBeepBuzzer = document.getElementById('cmdBeepBuzzer');
    const cmdSimFever = document.getElementById('cmdSimFever');
    const cmdSimNormal = document.getElementById('cmdSimNormal');

    // Modal Tabs & Buttons
    const modalTabBtns = document.querySelectorAll('.modal-tabs .tab-btn');
    const modalTabContents = document.querySelectorAll('.tab-content');
    const btnBleConnect = document.getElementById('btnBleConnect');
    const btnBleDisconnect = document.getElementById('btnBleDisconnect');
    const bleStatusText = document.getElementById('bleStatusText');
    const bleDot = document.getElementById('bleDot');

    const btnWifiSseConnect = document.getElementById('btnWifiSseConnect');
    const btnWifiDirectPoll = document.getElementById('btnWifiDirectPoll');
    const wifiEsp32Ip = document.getElementById('wifiEsp32Ip');
    const btnWifiDisconnect = document.getElementById('btnWifiDisconnect');

    // Device Port & Serial Elements
    const pillBoardEsp32 = document.getElementById('pillBoardEsp32');
    const pillBoardUno = document.getElementById('pillBoardUno');
    const btnScanSerialPorts = document.getElementById('btnScanSerialPorts');
    const serialPortSelect = document.getElementById('serialPortSelect');
    const btnBackendSerialConnect = document.getElementById('btnBackendSerialConnect');
    const btnSerialConnect = document.getElementById('btnSerialConnect');
    const btnSerialDisconnect = document.getElementById('btnSerialDisconnect');
    const serialBaudRate = document.getElementById('serialBaudRate');
    const serialStatusText = document.getElementById('serialStatusText');
    const serialDot = document.getElementById('serialDot');
    const cmdResetCounter = document.getElementById('cmdResetCounter');

    const btnSimToggle = document.getElementById('btnSimToggle');
    const simTemp = document.getElementById('simTemp');
    const simTempVal = document.getElementById('simTempVal');
    const simHR = document.getElementById('simHR');
    const simHRVal = document.getElementById('simHRVal');
    const simSpO2 = document.getElementById('simSpO2');
    const simSpO2Val = document.getElementById('simSpO2Val');
    const simAQI = document.getElementById('simAQI');
    const simAQIVal = document.getElementById('simAQIVal');
    const simPresetFever = document.getElementById('simPresetFever');
    const simPresetNormal = document.getElementById('simPresetNormal');
    const simPresetTachycardia = document.getElementById('simPresetTachycardia');

    const esp32TerminalBody = document.getElementById('esp32TerminalBody');
    const btnClearLog = document.getElementById('btnClearLog');

    let currentTempUnit = 'C';
    let sampleCasesCache = null;
    let latestPredictionData = null;

    /* ==========================================================================
       1. Theme Toggle & Persistence
       ========================================================================== */
    const savedTheme = localStorage.getItem('relivio_theme') || 'light';
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-theme');
        themeToggle.innerHTML = '<i class="fa-solid fa-sun"></i>';
    }

    themeToggle.addEventListener('click', () => {
        document.body.classList.toggle('dark-theme');
        const isDark = document.body.classList.contains('dark-theme');
        localStorage.setItem('relivio_theme', isDark ? 'dark' : 'light');
        themeToggle.innerHTML = isDark ? '<i class="fa-solid fa-sun"></i>' : '<i class="fa-solid fa-moon"></i>';
    });

    /* ==========================================================================
       2. Temperature Unit & Slider Synchronization
       ========================================================================== */
    function updateTempIndicator(tempC) {
        if (!tempIndicator) return;
        if (tempC < 37.3) {
            tempIndicator.innerHTML = '<span class="temp-state normal"><i class="fa-solid fa-circle-check"></i> Normal (&lt; 37.3°C)</span>';
        } else if (tempC <= 38.0) {
            tempIndicator.innerHTML = '<span class="temp-state mild"><i class="fa-solid fa-circle-dot"></i> Mild Fever (37.3°C - 38.0°C)</span>';
        } else {
            tempIndicator.innerHTML = '<span class="temp-state high"><i class="fa-solid fa-fire"></i> High Fever (&gt; 38.0°C)</span>';
        }
    }

    function autoSuggestFeverSeverity(tempC) {
        if (!feverSeveritySelect) return;
        if (tempC < 37.3) {
            feverSeveritySelect.value = 'Normal';
        } else if (tempC <= 38.0) {
            feverSeveritySelect.value = 'Mild Fever';
        } else {
            feverSeveritySelect.value = 'High Fever';
        }
    }

    function syncTemperatureFromSlider() {
        const val = parseFloat(tempSlider.value);
        if (currentTempUnit === 'C') {
            tempInput.value = val.toFixed(1);
            updateTempIndicator(val);
            autoSuggestFeverSeverity(val);
        } else {
            const valF = (val * 9/5) + 32;
            tempInput.value = valF.toFixed(1);
            updateTempIndicator(val);
            autoSuggestFeverSeverity(val);
        }
    }

    function syncTemperatureFromInput() {
        let val = parseFloat(tempInput.value) || 37.0;
        let tempC = val;
        if (currentTempUnit === 'F') {
            tempC = (val - 32) * 5/9;
        }
        tempSlider.value = Math.min(Math.max(tempC, 35.5), 41.0);
        updateTempIndicator(tempC);
        autoSuggestFeverSeverity(tempC);
    }

    tempSlider.addEventListener('input', syncTemperatureFromSlider);
    tempInput.addEventListener('input', syncTemperatureFromInput);

    tempUnitBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const newUnit = btn.dataset.unit;
            if (newUnit === currentTempUnit) return;

            tempUnitBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            let val = parseFloat(tempInput.value) || 37.0;
            if (newUnit === 'F') {
                val = (val * 9/5) + 32;
                tempInput.min = 95.0;
                tempInput.max = 107.0;
            } else {
                val = (val - 32) * 5/9;
                tempInput.min = 35.0;
                tempInput.max = 42.0;
            }
            currentTempUnit = newUnit;
            tempUnitDisplay.textContent = `°${newUnit}`;
            tempInput.value = val.toFixed(1);
        });
    });

    /* ==========================================================================
       3. Sliders Dynamic Label Updates (AQI & Humidity)
       ========================================================================== */
    function getAqiDescription(val) {
        if (val <= 50) return `${val} (Good)`;
        if (val <= 100) return `${val} (Moderate)`;
        if (val <= 150) return `${val} (Sensitive)`;
        if (val <= 200) return `${val} (Unhealthy)`;
        return `${val} (Hazardous)`;
    }

    aqiSlider.addEventListener('input', (e) => {
        aqiChip.textContent = getAqiDescription(e.target.value);
    });

    humiditySlider.addEventListener('input', (e) => {
        humidityChip.textContent = `${e.target.value}%`;
    });

    /* ==========================================================================
       4. BMI Helper Calculator
       ========================================================================== */
    toggleBmiCalc.addEventListener('click', () => {
        bmiCalcBox.classList.toggle('hidden');
    });

    function calculateBmi() {
        const h = parseFloat(calcHeight.value) / 100;
        const w = parseFloat(calcWeight.value);
        if (h > 0 && w > 0) {
            const bmi = w / (h * h);
            bmiInput.value = bmi.toFixed(1);
        }
    }

    calcHeight.addEventListener('input', calculateBmi);
    calcWeight.addEventListener('input', calculateBmi);

    /* ==========================================================================
       5. Symptom Switches Hidden Input Sync
       ========================================================================== */
    const symptomCheckboxes = [
        { cb: 'headacheSwitch', hid: 'headache' },
        { cb: 'bodyAcheSwitch', hid: 'bodyAche' },
        { cb: 'fatigueSwitch', hid: 'fatigue' },
        { cb: 'chronicSwitch', hid: 'chronic' },
        { cb: 'allergiesSwitch', hid: 'allergies' }
    ];

    symptomCheckboxes.forEach(({ cb, hid }) => {
        const elCb = document.getElementById(cb);
        const elHid = document.getElementById(hid);
        if (elCb && elHid) {
            elCb.addEventListener('change', () => {
                elHid.value = elCb.checked ? 'Yes' : 'No';
            });
        }
    });

    /* ==========================================================================
       6. Preset Scenarios Loader
       ========================================================================== */
    async function loadPresetCase(caseKey) {
        if (!sampleCasesCache) {
            try {
                const res = await fetch('/api/sample-cases');
                const data = await res.json();
                if (data.success) {
                    sampleCasesCache = data.cases;
                }
            } catch (err) {
                showToast('Failed to fetch sample cases', 'error');
                return;
            }
        }

        const selectedCase = sampleCasesCache[caseKey];
        if (!selectedCase) return;

        const d = selectedCase.data;

        // Populate Form Fields
        let tempVal = d.Temperature;
        if (currentTempUnit === 'F') {
            tempVal = (tempVal * 9/5) + 32;
        }
        tempInput.value = tempVal.toFixed(1);
        tempSlider.value = d.Temperature.toFixed(1);
        updateTempIndicator(d.Temperature);
        feverSeveritySelect.value = d.Fever_Severity;

        document.getElementById('age').value = d.Age;
        document.getElementById('bmi').value = d.BMI;
        document.getElementById('heartRate').value = d.Heart_Rate;

        // Gender
        const genderRadio = document.querySelector(`input[name="Gender"][value="${d.Gender}"]`);
        if (genderRadio) genderRadio.checked = true;

        // Blood Pressure
        const bpRadio = document.querySelector(`input[name="Blood_Pressure"][value="${d.Blood_Pressure}"]`);
        if (bpRadio) bpRadio.checked = true;

        // Symptoms
        symptomCheckboxes.forEach(({ cb, hid }) => {
            const key = hid.charAt(0).toUpperCase() + hid.slice(1);
            let val = d[key] || d[hid] || d['Chronic_Conditions'] || d['Body_Ache'];
            if (hid === 'bodyAche') val = d['Body_Ache'];
            if (hid === 'chronic') val = d['Chronic_Conditions'];

            const isYes = val === 'Yes';
            const elCb = document.getElementById(cb);
            const elHid = document.getElementById(hid);
            if (elCb && elHid) {
                elCb.checked = isYes;
                elHid.value = isYes ? 'Yes' : 'No';
            }
        });

        document.getElementById('previousMedication').value = d.Previous_Medication;
        document.getElementById('physicalActivity').value = d.Physical_Activity;
        document.getElementById('dietType').value = d.Diet_Type;

        const smkRadio = document.querySelector(`input[name="Smoking_History"][value="${d.Smoking_History}"]`);
        if (smkRadio) smkRadio.checked = true;

        const alcRadio = document.querySelector(`input[name="Alcohol_Consumption"][value="${d.Alcohol_Consumption}"]`);
        if (alcRadio) alcRadio.checked = true;

        aqiSlider.value = d.AQI;
        aqiChip.textContent = getAqiDescription(d.AQI);

        humiditySlider.value = d.Humidity;
        humidityChip.textContent = `${d.Humidity}%`;

        showToast(`Loaded preset: ${selectedCase.title}`, 'info');
    }

    presetPills.forEach(pill => {
        pill.addEventListener('click', () => {
            presetPills.forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            const caseKey = pill.dataset.case;
            loadPresetCase(caseKey);
        });
    });

    /* ==========================================================================
       7. Prediction Form Submit Handler
       ========================================================================== */
    predictionForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        let tempVal = parseFloat(tempInput.value) || 37.0;
        if (currentTempUnit === 'F') {
            tempVal = (tempVal - 32) * 5/9;
        }

        const formData = {
            Temperature: parseFloat(tempVal.toFixed(1)),
            Fever_Severity: feverSeveritySelect.value,
            Age: parseInt(document.getElementById('age').value) || 30,
            Gender: document.querySelector('input[name="Gender"]:checked').value,
            BMI: parseFloat(bmiInput.value) || 22.0,
            Headache: document.getElementById('headache').value,
            Body_Ache: document.getElementById('bodyAche').value,
            Fatigue: document.getElementById('fatigue').value,
            Chronic_Conditions: document.getElementById('chronic').value,
            Allergies: document.getElementById('allergies').value,
            Smoking_History: document.querySelector('input[name="Smoking_History"]:checked').value,
            Alcohol_Consumption: document.querySelector('input[name="Alcohol_Consumption"]:checked').value,
            Humidity: parseFloat(humiditySlider.value),
            AQI: parseInt(aqiSlider.value),
            Physical_Activity: document.getElementById('physicalActivity').value,
            Diet_Type: document.getElementById('dietType').value,
            Heart_Rate: parseInt(document.getElementById('heartRate').value) || 75,
            Blood_Pressure: document.querySelector('input[name="Blood_Pressure"]:checked').value,
            Previous_Medication: document.getElementById('previousMedication').value
        };

        // UI Loading state
        predictBtn.disabled = true;
        predictBtn.querySelector('.btn-spinner').classList.remove('hidden');
        predictBtn.querySelector('.btn-icon').classList.add('hidden');

        try {
            const resp = await fetch('/api/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData)
            });

            const result = await resp.json();
            if (result.success) {
                latestPredictionData = result;
                renderPredictionResults(result);
                showToast(`Recommended: ${result.prediction} (${result.confidence_percentage}%)`, 'success');
            } else {
                showToast(`Error: ${result.error}`, 'error');
            }
        } catch (err) {
            showToast(`Connection error: ${err.message}`, 'error');
        } finally {
            predictBtn.disabled = false;
            predictBtn.querySelector('.btn-spinner').classList.add('hidden');
            predictBtn.querySelector('.btn-icon').classList.remove('hidden');
        }
    });

    /* ==========================================================================
       8. Results Renderer
       ========================================================================== */
    function renderPredictionResults(res) {
        resultPlaceholder.classList.add('hidden');
        resultContent.classList.remove('hidden');

        const isParacetamol = res.prediction === 'Paracetamol';

        // Set theme on hero
        if (isParacetamol) {
            predictionHero.classList.remove('ibuprofen-theme');
            medIcon.innerHTML = '<i class="fa-solid fa-pills"></i>';
            medTypeLabel.textContent = 'Antipyretic & Analgesic (Acetaminophen)';
        } else {
            predictionHero.classList.add('ibuprofen-theme');
            medIcon.innerHTML = '<i class="fa-solid fa-capsules"></i>';
            medTypeLabel.textContent = 'Non-Steroidal Anti-Inflammatory Drug (NSAID)';
        }

        medName.textContent = res.prediction;
        confidenceBadge.textContent = `${res.confidence_percentage}% Confidence`;

        // Probabilities
        const pProb = res.probabilities['Paracetamol'] || 0;
        const iProb = res.probabilities['Ibuprofen'] || 0;

        paracetamolProb.textContent = `${pProb}%`;
        paracetamolFill.style.width = `${pProb}%`;

        ibuprofenProb.textContent = `${iProb}%`;
        ibuprofenFill.style.width = `${iProb}%`;

        // Clinical guidance
        const g = res.guidance || {};
        dosageText.textContent = g.dosage_info || 'Consult physician for standard dosing.';
        mechanismText.textContent = g.mechanism || 'Standard antipyretic mechanism.';

        // Cautions
        if (g.precautions && g.precautions.length > 0) {
            cautionsContainer.classList.remove('hidden');
            cautionsList.innerHTML = g.precautions.map(p => `<li><i class="fa-solid fa-triangle-exclamation"></i> ${p}</li>`).join('');
        } else {
            cautionsContainer.classList.add('hidden');
        }

        // Insights
        if (g.clinical_insights && g.clinical_insights.length > 0) {
            insightsContainer.classList.remove('hidden');
            insightsList.innerHTML = g.clinical_insights.map(i => `<li><i class="fa-solid fa-circle-check"></i> ${i}</li>`).join('');
        }
    }

    // Reset button handler
    resetBtn.addEventListener('click', () => {
        predictionForm.reset();
        syncTemperatureFromInput();
        bmiCalcBox.classList.add('hidden');
        resultContent.classList.add('hidden');
        resultPlaceholder.classList.remove('hidden');
        showToast('Form reset to default baseline', 'info');
    });

    // Model accordion toggle
    toggleModelInfo.addEventListener('click', () => {
        modelInfoBody.classList.toggle('hidden');
        infoChevron.classList.toggle('rotated');
    });

    // Print Report
    printReportBtn.addEventListener('click', () => {
        window.print();
    });

    // Copy Result Text
    copyResultBtn.addEventListener('click', () => {
        if (!latestPredictionData) return;
        const r = latestPredictionData;
        const copyText = `Relivio MedPredict Clinical Summary\nRecommended Medication: ${r.prediction} (${r.confidence_percentage}% Confidence)\nDosage: ${r.guidance.dosage_info}\nMechanism: ${r.guidance.mechanism}`;
        navigator.clipboard.writeText(copyText).then(() => {
            showToast('Clinical summary copied to clipboard!', 'success');
        });
    });

    /* ==========================================================================
       9. Toast Notification Helper
       ========================================================================== */
    function showToast(message, type = 'info') {
        toast.textContent = message;
        toast.className = `toast ${type}`;
        toast.classList.remove('hidden');
        setTimeout(() => {
            toast.classList.add('hidden');
        }, 3500);
    }

    /* ==========================================================================
       10. ESP32 Real-Time Telemetry Hub & Modal Controller
       ========================================================================== */
    // Initialize Animated ECG Canvas
    if (window.esp32Hub) {
        window.esp32Hub.initEcgCanvas('ecgWaveCanvas');
    }

    // Selected hardware board state
    let selectedBoard = 'ESP32';

    // Helper: Fetch and render active Windows COM ports in select dropdown
    async function refreshComPorts() {
        if (!serialPortSelect) return;
        serialPortSelect.innerHTML = '<option value="">-- Scanning Windows COM Ports... --</option>';
        if (btnScanSerialPorts) {
            btnScanSerialPorts.innerHTML = '<i class="fa-solid fa-arrows-rotate fa-spin"></i> Scanning...';
        }
        
        try {
            const ports = await window.esp32Hub.fetchSerialPorts();
            serialPortSelect.innerHTML = '';
            
            if (!ports || ports.length === 0) {
                serialPortSelect.innerHTML = '<option value="">No COM ports detected (Check USB Cable/Driver)</option>';
            } else {
                let defaultSelected = false;
                ports.forEach(p => {
                    const opt = document.createElement('option');
                    opt.value = p.port;
                    const isBluetooth = p.board_hint && p.board_hint.includes('Bluetooth');
                    opt.textContent = `${p.port} - ${p.board_hint} (${p.description || 'Serial'})`;
                    
                    // Prioritize physical USB/UART COM ports over standard Bluetooth links
                    if (!defaultSelected && !isBluetooth) {
                        opt.selected = true;
                        defaultSelected = true;
                    }
                    serialPortSelect.appendChild(opt);
                });
                
                if (!defaultSelected && ports.length > 0) {
                    serialPortSelect.options[0].selected = true;
                }
            }
        } catch (err) {
            serialPortSelect.innerHTML = '<option value="">Error scanning ports</option>';
        } finally {
            if (btnScanSerialPorts) {
                btnScanSerialPorts.innerHTML = '<i class="fa-solid fa-arrows-rotate"></i> Scan Ports';
            }
        }
    }

    // Modal Open & Close Listeners
    const openModal = () => {
        esp32Modal.classList.remove('hidden');
        refreshComPorts(); // Auto-scan COM ports when modal opens
    };
    const closeModal = () => esp32Modal.classList.add('hidden');

    if (openEsp32ModalBtn) openEsp32ModalBtn.addEventListener('click', openModal);
    if (hudConnectBtn) hudConnectBtn.addEventListener('click', openModal);
    if (closeEsp32ModalBtn) closeEsp32ModalBtn.addEventListener('click', closeModal);
    
    // Close modal on outside backdrop click
    esp32Modal.addEventListener('click', (e) => {
        if (e.target === esp32Modal) closeModal();
    });

    // Modal Tabs switcher
    modalTabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            modalTabBtns.forEach(b => b.classList.remove('active'));
            modalTabContents.forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            const tabId = btn.dataset.tab;
            const targetContent = document.getElementById(tabId);
            if (targetContent) targetContent.classList.add('active');
            if (tabId === 'tab-serial') {
                refreshComPorts();
            }
        });
    });

    // Board Switcher (ESP32 vs Arduino Uno)
    if (pillBoardEsp32 && pillBoardUno) {
        pillBoardEsp32.addEventListener('click', () => {
            selectedBoard = 'ESP32';
            pillBoardEsp32.classList.add('active');
            pillBoardUno.classList.remove('active');
            serialBaudRate.value = '115200';
            window.esp32Hub.log('Target board set: ESP32 Dev Module (115200 Baud)', 'info');
        });

        pillBoardUno.addEventListener('click', () => {
            selectedBoard = 'Arduino Uno';
            pillBoardUno.classList.add('active');
            pillBoardEsp32.classList.remove('active');
            serialBaudRate.value = '115200';
            window.esp32Hub.log('Target board set: Arduino Uno (ATmega328P)', 'info');
        });
    }

    // Manual Scan Ports button
    if (btnScanSerialPorts) {
        btnScanSerialPorts.addEventListener('click', () => {
            refreshComPorts();
            showToast('Scanning Windows COM ports...', 'info');
        });
    }

    // Auto Sync Toggles
    if (hudAutoFillToggle) {
        hudAutoFillToggle.addEventListener('change', (e) => {
            window.esp32Hub.autoFillEnabled = e.target.checked;
        });
    }

    if (hudAutoPredictToggle) {
        hudAutoPredictToggle.addEventListener('change', (e) => {
            window.esp32Hub.autoPredictEnabled = e.target.checked;
        });
    }

    // ESP32 Telemetry Event Listener -> Update HUD Visualizer Cards
    window.esp32Hub.on('telemetry', (vitals) => {
        // Temperature HUD
        hudTemp.textContent = vitals.temperature.toFixed(1);
        if (vitals.temperature < 37.3) {
            hudTempChip.className = 'tile-chip normal';
            hudTempChip.textContent = 'Normothermic';
        } else if (vitals.temperature <= 38.0) {
            hudTempChip.className = 'tile-chip mild';
            hudTempChip.textContent = 'Mild Pyrexia';
        } else {
            hudTempChip.className = 'tile-chip high';
            hudTempChip.textContent = 'High Pyrexia';
        }

        // Heart Rate HUD
        hudHR.textContent = vitals.heartRate;
        ecgBpmVal.textContent = vitals.heartRate;
        if (vitals.heartRate > 95) {
            hudHRChip.className = 'tile-chip high';
            hudHRChip.textContent = 'Tachycardia';
        } else {
            hudHRChip.className = 'tile-chip normal';
            hudHRChip.textContent = 'Normal Rhythm';
        }

        // SpO2 HUD
        hudSpO2.textContent = vitals.spo2.toFixed(1);
        if (vitals.spo2 < 95) {
            hudSpO2Chip.className = 'tile-chip high';
            hudSpO2Chip.textContent = 'Low Oxygen';
        } else {
            hudSpO2Chip.className = 'tile-chip normal';
            hudSpO2Chip.textContent = 'Optimal Oxygen';
        }

        // Environment HUD
        hudAQI.textContent = vitals.aqi;
        hudEnvChip.textContent = `${Math.round(vitals.humidity)}% Hum`;

        // Packet counter
        hudPacketCounter.innerHTML = `<i class="fa-solid fa-arrow-down-wide-short"></i> Packets: ${vitals.packetCount}`;
    });

    // Hardware Hub Status Change Listener -> Update UI state & badges
    window.esp32Hub.on('status', ({ status, mode, deviceId }) => {
        const isConn = (status === 'connected');
        const isConnecting = (status === 'connecting');

        // Header pill
        headerIotLabel.textContent = isConn ? `${selectedBoard}: ${mode.toUpperCase()} Active` : (isConnecting ? 'Connecting...' : `${selectedBoard}: Disconnected`);
        headerIotRing.parentElement.className = `btn-iot-pill ${status}`;

        // HUD Live indicator
        if (isConn) {
            hudLiveDot.parentElement.className = 'hud-live-indicator active';
            hudLiveText.textContent = `${selectedBoard.toUpperCase()} LIVE`;
            hudDeviceName.textContent = deviceId || `${selectedBoard} Node`;
            hudProtocolBadge.innerHTML = `<i class="fa-solid fa-signal"></i> ${mode.toUpperCase()} Active`;
            hudConnectBtn.innerHTML = '<i class="fa-solid fa-sliders"></i> Hardware Controls';
        } else {
            hudLiveDot.parentElement.className = 'hud-live-indicator';
            hudLiveText.textContent = `${selectedBoard.toUpperCase()} STANDBY`;
            hudDeviceName.textContent = 'No Device Linked';
            hudProtocolBadge.innerHTML = '<i class="fa-solid fa-network-wired"></i> Ready';
            hudConnectBtn.innerHTML = '<i class="fa-solid fa-satellite-dish"></i> Connect Hardware';
        }

        // BLE Modal button states
        if (mode === 'ble') {
            bleDot.className = `status-indicator-dot ${status}`;
            bleStatusText.textContent = isConn ? `Connected to ${deviceId}` : (isConnecting ? 'Connecting to ESP32 GATT...' : 'Ready to pair with ESP32');
            btnBleConnect.classList.toggle('hidden', isConn);
            btnBleDisconnect.classList.toggle('hidden', !isConn);
        }

        // Serial Modal button states
        if (mode === 'serial') {
            if (serialDot) serialDot.className = `status-indicator-dot ${status}`;
            if (serialStatusText) {
                serialStatusText.textContent = isConn 
                    ? `Connected to ${deviceId} (${selectedBoard}) • Live Streaming`
                    : (isConnecting ? `Opening COM Port for ${selectedBoard}...` : 'No COM Port Connected • Click "Scan Ports" below');
            }
            if (btnBackendSerialConnect) btnBackendSerialConnect.classList.toggle('hidden', isConn);
            if (btnSerialConnect) btnSerialConnect.classList.toggle('hidden', isConn);
            if (btnSerialDisconnect) btnSerialDisconnect.classList.toggle('hidden', !isConn);
        }

        // WiFi Modal button states
        if (mode === 'wifi') {
            btnWifiDisconnect.classList.toggle('hidden', !isConn);
        }

        // Simulator button
        if (mode === 'simulator') {
            btnSimToggle.innerHTML = isConn ? '<i class="fa-solid fa-stop"></i> Stop Virtual Stream' : '<i class="fa-solid fa-play"></i> Start Virtual Stream';
            btnSimToggle.className = isConn ? 'btn btn-secondary' : 'btn btn-primary';
        }
    });

    // Diagnostic Terminal Log Listener
    window.esp32Hub.on('log', ({ time, message, type }) => {
        if (!esp32TerminalBody) return;
        const line = document.createElement('div');
        line.className = `terminal-line ${type}`;
        line.innerHTML = `<span class="t-time">[${time}]</span> ${message}`;
        esp32TerminalBody.appendChild(line);
        esp32TerminalBody.scrollTop = esp32TerminalBody.scrollHeight;
    });

    if (btnClearLog) {
        btnClearLog.addEventListener('click', () => {
            esp32TerminalBody.innerHTML = '<div class="terminal-line info"><span class="t-time">[00:00:00]</span> Diagnostic log cleared.</div>';
        });
    }

    // --------------------------------------------------------------------------
    // BLE Button Handlers
    // --------------------------------------------------------------------------
    btnBleConnect.addEventListener('click', async () => {
        try {
            await window.esp32Hub.connectBLE();
            showToast('Web Bluetooth ESP32 Connected!', 'success');
        } catch (err) {
            showToast(`BLE Connect: ${err.message}`, 'error');
        }
    });

    btnBleDisconnect.addEventListener('click', () => {
        window.esp32Hub.disconnectBLE();
        showToast('BLE Disconnected', 'info');
    });

    // --------------------------------------------------------------------------
    // WiFi Button Handlers
    // --------------------------------------------------------------------------
    btnWifiSseConnect.addEventListener('click', () => {
        window.esp32Hub.connectWiFiSSE();
        showToast('Subscribed to Relivio WiFi IoT Hub (SSE)', 'success');
    });

    btnWifiDirectPoll.addEventListener('click', () => {
        const ip = wifiEsp32Ip.value.trim();
        if (!ip) {
            showToast('Please enter ESP32 IP address', 'error');
            return;
        }
        window.esp32Hub.startWiFiDirectPolling(ip);
        showToast(`Polling ESP32 at ${ip}...`, 'info');
    });

    btnWifiDisconnect.addEventListener('click', () => {
        window.esp32Hub.disconnectWiFi();
        showToast('WiFi stream disconnected', 'info');
    });

    // --------------------------------------------------------------------------
    // Hardware Device Port & Serial Button Handlers (PySerial & Web Serial)
    // --------------------------------------------------------------------------
    if (btnBackendSerialConnect) {
        btnBackendSerialConnect.addEventListener('click', async () => {
            const port = serialPortSelect ? serialPortSelect.value : '';
            const baud = serialBaudRate ? serialBaudRate.value : 115200;
            if (!port) {
                showToast('Please select a COM port first (or click Scan Ports)', 'error');
                return;
            }

            try {
                btnBackendSerialConnect.disabled = true;
                btnBackendSerialConnect.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Connecting...';
                await window.esp32Hub.connectBackendSerial(port, baud, selectedBoard);
                showToast(`Server connected to ${port} (${selectedBoard})!`, 'success');
            } catch (err) {
                showToast(`Serial error: ${err.message}`, 'error');
            } finally {
                btnBackendSerialConnect.disabled = false;
                btnBackendSerialConnect.innerHTML = '<i class="fa-solid fa-plug"></i> Connect via Server (PySerial)';
            }
        });
    }

    if (btnSerialConnect) {
        btnSerialConnect.addEventListener('click', async () => {
            const baud = serialBaudRate ? serialBaudRate.value : 115200;
            try {
                await window.esp32Hub.connectSerial(baud, selectedBoard);
                showToast(`${selectedBoard} Web Serial Connected!`, 'success');
            } catch (err) {
                showToast(`Serial: ${err.message}`, 'error');
            }
        });
    }

    if (btnSerialDisconnect) {
        btnSerialDisconnect.addEventListener('click', async () => {
            await window.esp32Hub.disconnectSerial();
            showToast('Serial port closed', 'info');
        });
    }

    // Additional hardware command
    if (cmdResetCounter) {
        cmdResetCounter.addEventListener('click', () => {
            window.esp32Hub.sendCommand('RESET');
            showToast('Dispatched RESET command', 'info');
        });
    }

    // --------------------------------------------------------------------------
    // Virtual Simulator Controls
    // --------------------------------------------------------------------------
    btnSimToggle.addEventListener('click', () => {
        if (window.esp32Hub.activeMode === 'simulator') {
            window.esp32Hub.stopSimulator();
        } else {
            window.esp32Hub.startSimulator(1000);
            showToast('Virtual ESP32 Simulator running!', 'success');
        }
    });

    simTemp.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        simTempVal.textContent = `${val.toFixed(1)}°C`;
        window.esp32Hub.simConfig.temp = val;
    });

    simHR.addEventListener('input', (e) => {
        const val = parseInt(e.target.value);
        simHRVal.textContent = `${val} BPM`;
        window.esp32Hub.simConfig.hr = val;
    });

    simSpO2.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        simSpO2Val.textContent = `${val.toFixed(1)}%`;
        window.esp32Hub.simConfig.spo2 = val;
    });

    simAQI.addEventListener('input', (e) => {
        const val = parseInt(e.target.value);
        simAQIVal.textContent = `${val}`;
        window.esp32Hub.simConfig.aqi = val;
    });

    // Simulator Quick Presets
    simPresetFever.addEventListener('click', () => {
        simTemp.value = 39.2;
        simTempVal.textContent = '39.2°C';
        simHR.value = 96;
        simHRVal.textContent = '96 BPM';
        window.esp32Hub.simConfig.temp = 39.2;
        window.esp32Hub.simConfig.hr = 96;
        window.esp32Hub.simConfig.bodyAche = 'Yes';
        window.esp32Hub.simConfig.headache = 'Yes';
        showToast('Simulated High Fever Profile', 'info');
    });

    simPresetNormal.addEventListener('click', () => {
        simTemp.value = 36.6;
        simTempVal.textContent = '36.6°C';
        simHR.value = 72;
        simHRVal.textContent = '72 BPM';
        window.esp32Hub.simConfig.temp = 36.6;
        window.esp32Hub.simConfig.hr = 72;
        window.esp32Hub.simConfig.bodyAche = 'No';
        window.esp32Hub.simConfig.headache = 'No';
        window.esp32Hub.simConfig.fatigue = 'No';
        showToast('Simulated Normal Baseline Profile', 'info');
    });

    simPresetTachycardia.addEventListener('click', () => {
        simTemp.value = 38.5;
        simTempVal.textContent = '38.5°C';
        simHR.value = 115;
        simHRVal.textContent = '115 BPM';
        window.esp32Hub.simConfig.temp = 38.5;
        window.esp32Hub.simConfig.hr = 115;
        showToast('Simulated Tachycardia Profile', 'info');
    });

    // --------------------------------------------------------------------------
    // Quick Hardware Commands
    // --------------------------------------------------------------------------
    cmdSampleNow.addEventListener('click', () => {
        window.esp32Hub.sendCommand('SAMPLE_NOW');
        showToast('Dispatched SAMPLE_NOW command', 'info');
    });

    cmdToggleLed.addEventListener('click', () => {
        window.esp32Hub.sendCommand('LED_TOGGLE');
        showToast('Dispatched LED_TOGGLE command', 'info');
    });

    cmdBeepBuzzer.addEventListener('click', () => {
        window.esp32Hub.sendCommand('BEEP');
        showToast('Dispatched BEEP command', 'info');
    });

    cmdSimFever.addEventListener('click', () => {
        window.esp32Hub.sendCommand('FEVER_HIGH');
        showToast('Sent FEVER_HIGH command to ESP32', 'info');
    });

    cmdSimNormal.addEventListener('click', () => {
        window.esp32Hub.sendCommand('FEVER_NORMAL');
        showToast('Sent FEVER_NORMAL command to ESP32', 'info');
    });

    // Initial default preset load
    loadPresetCase('mild_fever');
});
