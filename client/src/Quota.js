import React from 'react';
import { TextField, Grid, MenuItem, Box, CircularProgress } from '@material-ui/core';

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
            valid: this.props.validator.validate(value, this.props.validation).errors.length == 0
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
                            InputProps={{
                                readOnly: !Array.isArray(this.state.units),
                            }}
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

        this.props.edit(this.props.name, quota)
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

class Quota extends React.Component {

    constructor(props) {
        super(props);

        this.state = {
            quota: null,
            scheme: null,
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

                    for (const resourcequota_name in scheme) {
                        quota[resourcequota_name] = {}
                        for (const parameter_name in scheme[resourcequota_name]) {
                            quota[resourcequota_name][parameter_name] = {}
                            quota[resourcequota_name][parameter_name]["value"] = "0"
                            quota[resourcequota_name][parameter_name]["units"] = Array.isArray(scheme[resourcequota_name][parameter_name]["units"]) ? scheme[resourcequota_name][parameter_name]["units"][0] : scheme[resourcequota_name][parameter_name]["units"]
                        }
                    }

                } else {
                    quota = JSON.parse(JSON.stringify(this.props.current))
                }

                // fetch validation schema
                this.props.request('GET', '/validation/scheme', {}, {}, function(response, ok) {

                    let validation = JSON.parse(response)

                    if (ok) {

                        this.setState({
                            scheme: scheme,
                            quota: quota,
                            validation: validation,
                            validation_errors: this.validate(quota, validation)
                        }, function() {
                            this.props.handleChange(this.state.quota, this.state.validation_errors === "")
                        }.bind(this))

                    } else {
                        this.props.handleError(validation["message"])
                    }

                }.bind(this))
                
            } else {
                this.props.handleError(scheme["message"])
            }

        }.bind(this))

    }

    edit(name, value) {

        let quota = this.state.quota

        quota[name] = value

        this.setState({
            quota: quota,
            validation_errors: this.validate(quota, this.state.validation)
        }, function() {
            this.props.handleChange(this.state.quota, this.state.validation_errors === "")
        })
    }

    render() {

        return this.state.validation != null ? (
            Object.keys(this.state.scheme).map(quota_object_name =>
                <Grid item xs={12 / Object.keys(this.state.scheme).length}>
                    <ResourceQuota
                        name={quota_object_name}
                        fields={this.state.scheme[quota_object_name]}
                        validation={this.state.validation["properties"][quota_object_name]}
                        validator={this.props.validator}
                        edit={this.edit}
                        current={this.state.quota[quota_object_name]}></ResourceQuota>
                </Grid>
            )
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