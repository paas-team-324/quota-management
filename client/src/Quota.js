import React from 'react';
import { TextField, Grid, MenuItem, Box } from '@material-ui/core';

class QuotaParameter extends React.Component {

    constructor(props) {
        super(props);

        this.state = {
            name: this.props.parameter["name"],
            units: this.props.parameter["units"],
            regex: new RegExp(this.props.parameter["regex"]),
            regex_description: this.props.parameter["regex_description"],

            value: this.props.current["value"],
            selected_units: this.props.current["units"]
        };

        this.validate = this.validate.bind(this)
    };

    validate(value) {
 
        // test input with regex
        if (value === '' || this.state.regex.test(value)) {

            // set field text
            this.setState({
                value: value,
            })

            // edit quota object
            this.props.edit(this.props.parameter_name, value, this.state.selected_units)
        }

    }

    render() {
        return (
            <Box width="100%" style={{ marginTop: '4%', display: "flex" }}>
                <Grid item xs={ this.state.units === "" ? 12 : 10 }>
                    <TextField
                        id={this.props.parameter_name}
                        name={this.props.parameter_name}
                        label={this.state.name}
                        helperText={this.state.regex_description}
                        value={this.state.value}
                        onChange={event => this.validate(event.target.value)}
                        fullWidth
                    />
                </Grid>
                { this.state.units !== "" &&
                    <Grid item xs={2}>
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
                            InputProps={{
                                readOnly: !Array.isArray(this.state.units),
                                style: { marginLeft: '7%' }
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

        // if empty - remove from quota
        if (value === '') {
            delete quota[name]
        } else {
            quota[name] = {
                "value": value,
                "units": units,
            }
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
                edit={this.edit}
                current={this.props.current[parameter_name]}></QuotaParameter>
        )
        
    }

}

class Quota extends React.Component {

    constructor(props) {
        super(props);

        this.state = {
            quota: JSON.parse(JSON.stringify(this.props.current)),
            filled: true
        };

        this.edit = this.edit.bind(this)
    };

    edit(name, value) {

        let quota = this.state.quota

		// if not all keys are set - remove from final output
        if (Object.keys(value).length === Object.keys(this.props.scheme[name]).length) {
            quota[name] = value
        } else {
            delete quota[name]
        }

        this.setState({
            quota: quota,
        })

        let filled = (Object.keys(quota).length === Object.keys(this.props.scheme).length ? true : false)
        this.props.handleChange(quota, filled)
    }

    render() {

        return Object.keys(this.props.scheme).map(quota_object_name =>
            <Grid item xs={12 / Object.keys(this.props.scheme).length}>
                <ResourceQuota
                    name={quota_object_name}
                    fields={this.props.scheme[quota_object_name]}
                    edit={this.edit}
                    current={this.props.current[quota_object_name]}></ResourceQuota>
            </Grid>
        )

    }
}

export default Quota;