import React from 'react';
import { TextField, Grid, MenuItem, Box, CircularProgress, Divider, Typography } from '@mui/material';
import { Autocomplete } from '@mui/lab';

const DATA_TYPE_DESCRIPTIONS = {
    "int": "Whole non-negative number",
    "float": "Floating point non-negative number"
}

class QuotaParameter extends React.Component {

    constructor(props) {
        super(props);

        this.state = {
            name: this.props.parameter["name"],
            units: this.props.parameter["units"],

            value: this.props.current["value"],
            selected_units: this.props.current["units"],
            valid: true
        };

        this.validate = this.validate.bind(this)
    };

    validate(value) {

        // set field text and check for validation errors
        this.setState({
            value: value,
            valid: this.props.validator.validate(value, this.props.validation).errors.length === 0
        })

        // edit quota object
        this.props.edit(this.props.parameter_name, value, this.state.selected_units)
        
    }

    render() {
        return (
            <Box width="100%" style={{ marginTop: '4%', display: "flex" }}>
                <Grid item xs={ this.state.units === "" ? 12 : 10 }>
                    <TextField
                        id={this.props.parameter_name}
                        name={this.props.parameter_name}
                        label={this.state.name}
                        helperText={DATA_TYPE_DESCRIPTIONS[this.props.parameter["type"]]}
                        value={this.state.value}
                        onChange={event => this.validate(event.target.value)}
                        error={!this.state.valid}
                        InputLabelProps={{ shrink: true }}
                        variant="standard"
                        fullWidth
                    />
                </Grid>
                { this.state.units !== "" &&
                    <Grid item xs={2} style={{ paddingLeft: '2%', textAlign: "center" }}>
                        <TextField
                            id={this.props.parameter_name + "_units"}
                            name={this.props.parameter_name + "_units"}
                            label=" "
                            helperText=" "
                            value={ this.state.selected_units }
                            select={Array.isArray(this.state.units)}
                            onChange={event => {
                                this.setState({
                                    selected_units: event.target.value
                                }, function() {
                                    this.validate(this.state.value)
                                })
                            }}
                            inputProps={{ style: { textAlign: "center" } }}
                            // eslint-disable-next-line
                            InputProps={{
                                readOnly: !Array.isArray(this.state.units),
                            }}
                            variant="standard"
                            fullWidth
                        >
                        { Array.isArray(this.state.units) &&
                            this.state.units.map(unit => 
                                <MenuItem value={unit}>{unit}</MenuItem>
                            )
                        }
                        </TextField>
                    </Grid>
                }
            </Box>
        )
    }

}

class ResourceQuota extends React.Component {

    constructor(props) {
        super(props);

        this.state = {
            quota: JSON.parse(JSON.stringify(this.props.current))
        };

        this.edit = this.edit.bind(this)
    };

    edit(name, value, units) {

        let quota = this.state.quota

        quota[name] = {
            "value": value,
            "units": units,
        }

        this.setState({
            quota: quota
        })

        this.props.edit("quota", this.props.name, quota)
    }

    render() {

        return Object.keys(this.props.fields).map(parameter_name =>
            <QuotaParameter
                parameter_name={parameter_name}
                parameter={this.props.fields[parameter_name]}
                validation={this.props.validation["properties"][parameter_name]["properties"]["value"]}
                validator={this.props.validator}
                edit={this.edit}
                current={this.props.current[parameter_name]}></QuotaParameter>
        )
        
    }

}

class Label extends React.Component {

    constructor(props) {
        super(props);

        this.state = {
            value: this.props.current,
            valid: true
        };

        this.validate = this.validate.bind(this)
    };

    validate(value) {
        
        // set field text and check for validation errors
        this.setState({
            value: value,
            valid: this.props.validator.validate(value, this.props.validation).errors.length === 0
        })

        // edit quota object
        this.props.edit("labels", this.props.name, value)
        
    }

    render() {
        return (
            <Autocomplete
                id={this.props.name}
                name={this.props.name}
                defaultValue={this.props.current}
                onChange={ (event, value, reason) => this.validate(value)}
                freeSolo
                disableClearable
                fullWidth
                options={this.props.labels}
                renderInput={(params) => 
                    <TextField {...params}
                        label={this.props.displayname}
                        value={this.state.value}
                        onChange={event => this.validate(event.target.value)}
                        error={!this.state.valid}
                        InputLabelProps={{ shrink: true }}
                        variant="standard"
                        fullWidth
                    />}
            />
        )
    }

}

class Quota extends React.Component {

    constructor(props) {
        super(props);

        this.state = {
            quota: null,
            scheme: null,
            labels: null,
            validation: null,
            validation_errors: null
        };

        this.edit = this.edit.bind(this)
        this.validate = this.validate.bind(this)
    };

    validate(quota, schema) {
        return this.props.validator.validate(quota, schema).errors.map((error) => "* " + error.message).join("\n")
    }

    componentDidMount() {

        this.props.request('GET', '/scheme', {}, {}, function(response, ok) {

            let scheme = JSON.parse(response)

            if (ok) {

                let quota = {}

                // if current was not provided, init a zero value quota
                if (this.props.current == null) {

                    quota["labels"] = {}
                    quota["quota"] = {}

                    // init labels with empty values
                    for (const label_name in scheme["labels"]) {
                        quota["labels"][label_name] = ""
                    }

                    // init quota with empty values
                    for (const resourcequota_name in scheme["quota"]) {
                        quota["quota"][resourcequota_name] = {}
                        for (const parameter_name in scheme["quota"][resourcequota_name]) {
                            quota["quota"][resourcequota_name][parameter_name] = {}
                            quota["quota"][resourcequota_name][parameter_name]["value"] = "0"
                            quota["quota"][resourcequota_name][parameter_name]["units"] = Array.isArray(scheme["quota"][resourcequota_name][parameter_name]["units"]) ? scheme["quota"][resourcequota_name][parameter_name]["units"][0] : scheme["quota"][resourcequota_name][parameter_name]["units"]
                        }
                    }

                } else {
                    quota = JSON.parse(JSON.stringify(this.props.current))
                }

                // set UI width based on amount of quota objects
                this.props.setWidth(Object.keys(scheme["quota"]).length)

                // fetch validation schema
                this.props.request('GET', '/validation/scheme', {}, {}, function(response, ok) {

                    let validation = JSON.parse(response)

                    if (ok) {

                        let labels = null

                        // prepare finish mounting function
                        let finishMount = function() {

                            this.setState({
                                scheme: scheme,
                                quota: quota,
                                labels: labels,
                                validation: validation,
                                validation_errors: this.validate(quota, validation)
                            }, function() {
                                this.props.handleChange(this.state.quota, this.state.validation_errors === "")
                            }.bind(this))

                        }.bind(this)

                        // fetch list of labels if labeling is enabled
                        if (Object.keys(scheme["labels"]).length !== 0) {

                            this.props.request('GET', '/labels', {}, {}, function(response, ok) {

                                labels = JSON.parse(response)

                                if (ok) {
                                    finishMount()
                                } else {
                                    this.props.handleError(labels["message"])
                                }

                            }.bind(this))

                        } else {
                            finishMount()
                        }

                    } else {
                        this.props.handleError(validation["message"])
                    }

                }.bind(this))
                
            } else {
                this.props.handleError(scheme["message"])
            }

        }.bind(this))

    }

    edit(field, name, value) {

        let quota = this.state.quota

        quota[field][name] = value

        this.setState({
            quota: quota,
            validation_errors: this.validate(quota, this.state.validation)
        }, function() {
            this.props.handleChange(this.state.quota, this.state.validation_errors === "")
        })
    }

    render() {

        return this.state.validation != null ? (
            <Grid item xs={12}>

                {/* project quota divider (only render if labeling is enabled) */}
                {this.state.labels != null && (

                    <Divider style={{ marginBottom: '2%' }}>
                        <Typography variant="caption">
                            Labels
                        </Typography>
                    </Divider>

                )}

                <Grid container spacing={3}>

                    {/* project labels (only render if labeling is enabled) */}
                    {this.state.labels != null && (

                        Object.keys(this.state.scheme["labels"]).map(label =>
                            <Grid item xs={12 / Object.keys(this.state.scheme["quota"]).length / 2}>
                                <Label
                                    name={label}
                                    displayname={this.state.scheme["labels"][label]}
                                    current={this.state.quota["labels"][label]}
                                    labels={this.state.labels[label]}
                                    validation={this.state.validation["properties"]["labels"]["properties"][label]}
                                    validator={this.props.validator}
                                    edit={this.edit}
                                    ></Label>
                            </Grid>
                        )

                    )}
                    {this.state.labels != null && ( <Grid item xs={ 12 - ((12 / Object.keys(this.state.scheme["quota"]).length / 2) * Object.keys(this.state.scheme["labels"]).length) } /> )}
                    
                    {/* project quota divider */}
                    <Grid item xs={12} style={{ marginBottom: '-2%' }}>
                        <Divider>
                            <Typography variant="caption">
                                Quota
                            </Typography>
                        </Divider>
                    </Grid>

                    {/* project quota */}
                    {Object.keys(this.state.scheme["quota"]).map(quota_object_name =>
                        <Grid item xs={12 / Object.keys(this.state.scheme["quota"]).length}>
                            <ResourceQuota
                                name={quota_object_name}
                                fields={this.state.scheme["quota"][quota_object_name]}
                                validation={this.state.validation["properties"]["quota"]["properties"][quota_object_name]}
                                validator={this.props.validator}
                                edit={this.edit}
                                current={this.state.quota["quota"][quota_object_name]}></ResourceQuota>
                        </Grid>
                    )}

                </Grid>
            </Grid>
        ) : (
            <Grid item xs={12}>
                <div style={{display: 'flex', justifyContent:'center', alignItems:'center'}}>
                    <CircularProgress />
                </div>
            </Grid>
        )

    }
}

export default Quota;