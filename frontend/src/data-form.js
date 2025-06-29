import { useState } from 'react';
import {
    Box,
    TextField,
    Button,
} from '@mui/material';
import axios from 'axios';

const endpointMapping = {
    'notion': 'notion',
    'airtable': 'airtable',
    'hubspot': 'hubspot' 
};

export const DataForm = ({ integrationType, credentials }) => {
    const [loadedData, setLoadedData] = useState(null); 
    console.log("Integration Type:", integrationType); 
    const endpoint = endpointMapping[integrationType.toLowerCase()];
    console.log("Resolved Endpoint:", endpoint);
    console.log("Credentials =>", credentials); 

    const handleLoad = async () => {
        if (!endpoint) {
            alert("Invalid integration type");
            return;
        }
        try {
            const formData = new FormData();
            formData.append('credentials', JSON.stringify(credentials)); 
    
            const response = await axios.post(
                `http://localhost:8080/integrations/${endpoint}/load`,
                formData,
                { headers: { "Content-Type": "multipart/form-data" } } 
            );
    
            console.log("Credentials Sent:", credentials);
            const data = response.data;
            setLoadedData(data);
        } catch (e) {
            alert(e?.response?.data?.detail || "Failed to load data");
        }
    };

    return (
        <Box display="flex" justifyContent="center" alignItems="center" flexDirection="column" width="100%">
            <Box display="flex" flexDirection="column" width="100%">
                
                <TextField
                    label="Loaded Data"
                    multiline
                    value={loadedData ? JSON.stringify(loadedData, null, 2) : "No data loaded"} 
                    sx={{ mt: 2 }}
                    InputLabelProps={{ shrink: true }}
                    disabled
                />

                <Button onClick={handleLoad} sx={{ mt: 2 }} variant="contained">
                    Load Data
                </Button>
                <Button onClick={() => setLoadedData(null)} sx={{ mt: 1 }} variant="contained">
                    Clear Data
                </Button>
            </Box>
        </Box>
    );
};
