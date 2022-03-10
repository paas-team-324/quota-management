import React from 'react';
import Quota from './Quota'

import { Grid, Typography, Button, CircularProgress, TextField, InputAdornment, Tooltip } from '@mui/material';
import { Alert, AlertTitle } from '@mui/lab';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';

const create_button_idle = "Create"
const create_button_working = "Creating..."

class NewProject extends React.Component {

    constructor(props) {
        super(props)

        this.state = {
            project_name: "",
            project_name_validation: null,
            project_name_validation_errors: "",
            project_name_valid: false,

            admin_name: "",
            admin_name_validation: null,
            admin_name_validation_errors: "",
            admin_name_valid: false,

            quota: {},
            filled: false,

            create_button_text: create_button_idle,
            creating: false,
            error: null,
        }

        this.create = this.create.bind(this)
        this.set_name = this.set_name.bind(this)
    }

    create() {

        this.setState({
            creating: true,
            create_button_text: create_button_working
        })

        // create project
        this.props.request('POST', '/projects', { 
            project: this.state.project_name,
            admin: this.state.admin_name,
        }, this.state.quota, function(response, ok) {

            // create appropriate alert
            this.props.addAlert(JSON.parse(response)["message"], ok ? "success" : "error")

            this.setState({
                creating: false,
                create_button_text: create_button_idle
            })

        }.bind(this))

    }

    set_name(name, field, schema) {

        let validation = this.props.validator.validate(name, schema)

        this.setState({
            [field]: name,
            [field + "_valid"]: validation.errors.length === 0,
            [field + "_validation_errors"]: validation.errors.map((error) => "* " + error.message).join("\n")
        })

    }

    componentDidMount() {

        // fetch project name and username schemas
        let validations = { "project": "project_name_validation", "username": "admin_name_validation" }

        for (const validation in validations) {

            this.props.request('GET', '/validation/' + validation, {}, {}, function(response, ok) {

                let responseJSON = JSON.parse(response)
    
                if (ok) {
    
                    this.setState({
                        [validations[validation]]: responseJSON
                    })
    
                } else {
                    
                    this.setState({
                        error: responseJSON["message"]
                    })

                }
    
            }.bind(this))

        }

    }

    render() {
        return (
            <div>
                {this.state.error != null ? (
                    <Alert severity="error">
                        <AlertTitle>Error</AlertTitle>
                            {this.state.error}
                    </Alert>
                ) : (
                    <div>
                        {this.state.admin_name_validation == null || this.state.project_name_validation == null ? (
                            <div style={{display: 'flex', justifyContent:'center', alignItems:'center'}}>
                                <CircularProgress />
                            </div>
                        ) : (
                            <Grid container spacing={3}>
                                <Grid item xs={3}>
                                    <Typography gutterBottom>
                                        <TextField 
                                        id="project_name" 
                                        label="Name" 
                                        variant="standard"
                                        error={!this.state.project_name_valid && this.state.project_name.length !== 0}
                                        value={this.state.project_name}
                                        onChange={(event) => {
                                            this.set_name(event.target.value, "project_name", this.state.project_name_validation)
                                        }}
                                        InputProps={ !this.state.project_name_valid && this.state.project_name.length !== 0 ? {
                                            endAdornment: (
                                                <InputAdornment position="end">
                                                    <Tooltip title={this.state.project_name_validation_errors}>
                                                        <HelpOutlineIcon style={{cursor: 'default'}}/>
                                                    </Tooltip>
                                                </InputAdornment>
                                            )
                                        } : {} }
                                        InputLabelProps={{ shrink: true }}
                                        fullWidth />
                                    </Typography>
                                </Grid>
                                <Grid item xs={3}>
                                    <Typography gutterBottom>
                                        <TextField 
                                        id="admin_name" 
                                        label="Admin" 
                                        variant="standard"
                                        error={!this.state.admin_name_valid && this.state.admin_name.length !== 0}
                                        value={this.state.admin_name}
                                        onChange={(event) => {
                                            this.set_name(event.target.value, "admin_name", this.state.admin_name_validation)
                                        }}
                                        InputProps={ !this.state.admin_name_valid && this.state.admin_name.length !== 0 ? {
                                            endAdornment: (
                                                <InputAdornment position="end">
                                                    <Tooltip title={this.state.admin_name_validation_errors}>
                                                        <HelpOutlineIcon style={{cursor: 'default'}}/>
                                                    </Tooltip>
                                                </InputAdornment>
                                            )
                                        } : {} }
                                        InputLabelProps={{ shrink: true }}
                                        fullWidth />
                                    </Typography>
                                </Grid>
                                <Grid item xs={3}></Grid>
                                <Grid item xs={3}>
                                    <Button
                                        size="small"
                                        variant="contained"
                                        color="primary"
                                        component="span"
                                        disabled={this.state.creating || !this.state.admin_name_valid || !this.state.project_name_valid || !this.state.filled}
                                        fullWidth
                                        onClick={() => this.create()}>
                                        {this.state.create_button_text}
                                    </Button>
                                </Grid>
                                <Quota request={this.props.request} handleChange={(quota, filled) => {
                                    this.setState({
                                            quota: quota,
                                            filled: filled
                                    })
                                }} handleError={(error) => {
                                    this.setState({
                                        error: error
                                    })
                                }} current={null} validator={this.props.validator} setWidth={this.props.setWidth}></Quota>
                            </Grid>
                        )}
                    </div>
                )}
                
            </div>
        )
    }

}

export default NewProject;